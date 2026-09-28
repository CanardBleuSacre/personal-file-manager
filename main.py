import sys
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget)
import core

DB = Path.home() / '.local/share/personal-file-manager/history.sqlite3'


class DuplicateWorker(QObject):
    finished = Signal(object)
    def __init__(self, folder):
        super().__init__()
        self.folder = folder
    def run(self):
        try:
            self.finished.emit((core.duplicates(self.folder), None))
        except Exception as exc:
            self.finished.emit(([], str(exc)))


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Gestionnaire de fichiers personnel')
        self.resize(920, 620)
        self.folder = None
        self.plan = []
        self.thread = None
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        files = QWidget(); layout = QVBoxLayout(files)
        top = QHBoxLayout()
        self.location = QLabel('Aucun dossier sélectionné')
        choose = QPushButton('Choisir un dossier'); choose.clicked.connect(self.choose)
        top.addWidget(choose); top.addWidget(self.location, 1); layout.addLayout(top)
        actions = QHBoxLayout()
        self.action = QComboBox(); self.action.addItems(['Nettoyer les noms', 'Classer par type'])
        scan = QPushButton('Prévisualiser'); scan.clicked.connect(self.preview)
        apply = QPushButton('Appliquer'); apply.clicked.connect(self.apply)
        actions.addWidget(self.action); actions.addWidget(scan); actions.addWidget(apply)
        layout.addLayout(actions)
        self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(['Avant', 'Après'])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        tabs.addTab(files, 'Fichiers')
        history = QWidget(); hl = QVBoxLayout(history)
        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(['ID', 'Date', 'Avant', 'Après / état'])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        hl.addWidget(self.history_table)
        refresh = QPushButton('Actualiser'); refresh.clicked.connect(self.refresh_history)
        undo = QPushButton('Annuler la ligne sélectionnée'); undo.clicked.connect(self.undo)
        hl.addWidget(refresh); hl.addWidget(undo)
        tabs.addTab(history, 'Historique')
        duplicate_tab = QWidget(); dl = QVBoxLayout(duplicate_tab)
        self.duplicate_button = QPushButton('Chercher les doublons du dossier choisi')
        self.duplicate_button.clicked.connect(self.scan_duplicates)
        self.duplicate_list = QTableWidget(0, 2)
        self.duplicate_list.setHorizontalHeaderLabels(['Groupe', 'Fichier'])
        self.duplicate_list.horizontalHeader().setStretchLastSection(True)
        dl.addWidget(self.duplicate_button); dl.addWidget(self.duplicate_list)
        tabs.addTab(duplicate_tab, 'Doublons')
        self.refresh_history()

    def choose(self):
        folder = QFileDialog.getExistingDirectory(self, 'Choisir un dossier')
        if folder:
            self.folder = Path(folder)
            self.location.setText(folder)
            self.plan = []
            self.table.setRowCount(0)
            self.duplicate_list.setRowCount(0)

    def preview(self):
        if not self.folder:
            QMessageBox.information(self, 'Dossier', 'Choisis d’abord un dossier.'); return
        try:
            self.plan = core.preview(self.folder, 'rename' if self.action.currentIndex() == 0 else 'organize')
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Erreur', str(exc)); return
        self.table.setRowCount(len(self.plan))
        for row, (source, target) in enumerate(self.plan):
            for col, value in enumerate((str(source), str(target))):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.statusBar().showMessage(f'{len(self.plan)} modification(s) proposée(s)')

    def apply(self):
        if not self.plan:
            QMessageBox.information(self, 'Aperçu', 'Aucune modification à appliquer.'); return
        if QMessageBox.question(self, 'Confirmer', f'Appliquer {len(self.plan)} modification(s) ?') != QMessageBox.StandardButton.Yes:
            return
        try:
            DB.parent.mkdir(parents=True, exist_ok=True)
            results = core.apply(self.plan, DB)
            errors = [f'{source}: {err}' for source, _, err in results if err]
            self.plan = []
            self.preview(); self.refresh_history()
            QMessageBox.information(self, 'Résultat', f'{len(results)-len(errors)} réussite(s), {len(errors)} erreur(s).\n' + '\n'.join(errors[:5]))
        except OSError as exc:
            QMessageBox.warning(self, 'Erreur', str(exc))

    def refresh_history(self):
        try:
            rows = core.history(DB)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Historique', str(exc)); return
        self.history_table.setRowCount(len(rows))
        for row, (ident, date, source, target, undone) in enumerate(rows):
            for col, value in enumerate((ident, date, source, target + (' [annulé]' if undone else ''))):
                self.history_table.setItem(row, col, QTableWidgetItem(str(value)))

    def undo(self):
        row = self.history_table.currentRow()
        if row < 0:
            return
        ident = int(self.history_table.item(row, 0).text())
        if QMessageBox.question(self, 'Confirmer', f'Annuler l’action {ident} ?') != QMessageBox.StandardButton.Yes:
            return
        try:
            core.undo(ident, DB)
            self.refresh_history(); self.preview() if self.folder else None
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Annulation impossible', str(exc))

    def scan_duplicates(self):
        if not self.folder:
            QMessageBox.information(self, 'Dossier', 'Choisis d’abord un dossier.'); return
        self.duplicate_button.setEnabled(False)
        self.statusBar().showMessage('Recherche des doublons en cours…')
        self.thread = QThread()
        self.worker = DuplicateWorker(self.folder)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.show_duplicates)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def show_duplicates(self, result):
        groups, error = result
        self.duplicate_button.setEnabled(True)
        if error:
            QMessageBox.warning(self, 'Doublons', error); return
        items = [(i, path) for i, group in enumerate(groups, 1) for path in group]
        self.duplicate_list.setRowCount(len(items))
        for row, (i, path) in enumerate(items):
            self.duplicate_list.setItem(row, 0, QTableWidgetItem(str(i)))
            self.duplicate_list.setItem(row, 1, QTableWidgetItem(str(path)))
        self.statusBar().showMessage(f'{len(groups)} groupe(s) de doublons')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Window(); window.show()
    sys.exit(app.exec())
