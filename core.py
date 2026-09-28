"""Pure filesystem operations for the file manager."""
import hashlib
import re
import sqlite3
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CATEGORIES = {
    'Images': {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'},
    'Documents': {'.pdf', '.doc', '.docx', '.txt', '.odt', '.csv', '.xlsx'},
    'Archives': {'.zip', '.rar', '.7z', '.gz', '.tar'},
    'Videos': {'.mp4', '.mkv', '.mov', '.webm'},
    'Audio': {'.mp3', '.wav', '.flac', '.ogg'},
}


def clean(stem):
    stem = unicodedata.normalize('NFKD', stem)
    stem = ''.join(c for c in stem if not unicodedata.combining(c))
    return re.sub(r'[^\w.-]+', '_', stem, flags=re.ASCII).strip('._') or 'fichier'


def preview(folder, action):
    folder = Path(folder).resolve()
    if not folder.is_dir() or action not in ('rename', 'organize'):
        raise ValueError('Dossier ou action invalide')
    sources = [p for p in sorted(folder.iterdir()) if p.is_file() and not p.is_symlink()]
    occupied = {p.resolve() for p in folder.iterdir()}
    plan = []
    for source in sources:
        if action == 'rename':
            dest_dir, basename = folder, clean(source.stem) + source.suffix.lower()
        else:
            category = next((c for c, extensions in CATEGORIES.items() if source.suffix.lower() in extensions), 'Autres')
            dest_dir, basename = folder / category, source.name
        target = dest_dir / basename
        if target == source:
            continue
        root = Path(basename)
        n = 2
        while target.resolve() in occupied or target.exists():
            target = dest_dir / f'{root.stem}_{n}{root.suffix}'
            n += 1
        occupied.add(target.resolve())
        plan.append((source, target))
    return plan


def init_db(db):
    with sqlite3.connect(db) as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY, time TEXT NOT NULL, source TEXT NOT NULL, target TEXT NOT NULL, undone INTEGER NOT NULL DEFAULT 0)')


def move_checked(source, target):
    if not source.is_file() or source.is_symlink() or target.exists():
        raise FileExistsError(f'Source absente ou destination occupée : {source} -> {target}')
    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)


def apply(plan, db):
    init_db(db)
    results = []
    with sqlite3.connect(db) as connection:
        for source, target in plan:
            try:
                move_checked(source, target)
                try:
                    connection.execute('INSERT INTO actions(time,source,target) VALUES(?,?,?)', (datetime.now(timezone.utc).isoformat(), str(source), str(target)))
                    connection.commit()
                except sqlite3.Error:
                    target.rename(source)
                    raise
                results.append((source, target, None))
            except (OSError, sqlite3.Error) as exc:
                results.append((source, target, str(exc)))
    return results


def history(db, limit=100):
    init_db(db)
    with sqlite3.connect(db) as connection:
        return connection.execute('SELECT id,time,source,target,undone FROM actions ORDER BY id DESC LIMIT ?', (limit,)).fetchall()


def undo(action_id, db):
    init_db(db)
    with sqlite3.connect(db) as connection:
        row = connection.execute('SELECT source,target,undone FROM actions WHERE id=?', (action_id,)).fetchone()
        if row is None or row[2]:
            raise ValueError('Action introuvable ou déjà annulée')
        source, target = Path(row[0]), Path(row[1])
        move_checked(target, source)
        try:
            connection.execute('UPDATE actions SET undone=1 WHERE id=?', (action_id,))
            connection.commit()
        except sqlite3.Error:
            source.rename(target)
            raise


def duplicates(folder):
    sizes = defaultdict(list)
    for path in Path(folder).rglob('*'):
        if path.is_file() and not path.is_symlink():
            try:
                sizes[path.stat().st_size].append(path)
            except OSError:
                pass
    groups = []
    for paths in sizes.values():
        if len(paths) < 2:
            continue
        hashes = defaultdict(list)
        for path in paths:
            try:
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                hashes[digest.digest()].append(path)
            except OSError:
                pass
        groups.extend(group for group in hashes.values() if len(group) > 1)
    return groups
