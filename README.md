# Personal File Manager

Application de bureau Python pour ranger des fichiers, nettoyer leurs noms et repérer les doublons. Interface en français ; fonctionne localement sur Fedora KDE et les autres bureaux compatibles avec PySide6.

## Fonctionnalités

- Choisir un dossier et prévisualiser les changements avant de les appliquer.
- Nettoyer les noms (accents et caractères spéciaux) ou classer les fichiers par type.
- Conserver un historique et annuler une opération si l'ancien emplacement est libre.
- Afficher les groupes de fichiers identiques par comparaison de la taille et de l'empreinte SHA-256. Aucune suppression automatique.

Le renommage et le classement portent sur les fichiers directement présents dans le dossier choisi ; la recherche de doublons parcourt aussi ses sous-dossiers. Les liens symboliques sont ignorés.

## Installer et lancer

Python 3.10 ou plus récent est nécessaire. Dans un terminal ouvert à la racine du dépôt :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

Sous Fedora, lance le programme depuis ta session graphique KDE. Teste d'abord les actions sur des copies de fichiers.

## Utilisation

1. Clique sur **Choisir un dossier**.
2. Sélectionne **Nettoyer les noms** ou **Classer par type** et clique sur **Prévisualiser**.
3. Vérifie la colonne « Après », puis clique sur **Appliquer**.
4. Consulte **Historique** pour annuler une action individuelle, ou **Doublons** pour rechercher les copies identiques.

Avant chaque déplacement, le programme vérifie que la destination est libre. Un fichier modifié ou déplacé entre la prévisualisation et l'application peut provoquer une erreur pour cette ligne. L'historique local se trouve dans `~/.local/share/personal-file-manager/history.sqlite3`.

## Structure

- `main.py` : interface PySide6.
- `core.py` : renommage, classement, doublons et historique SQLite.
- `requirements.txt` : dépendance graphique.
- `.gitignore` : fichiers locaux exclus de Git.
