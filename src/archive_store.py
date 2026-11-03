"""Per-folder SQLite state: approved rules, checkpoints, duplicates and undo history.

No account credentials are stored here. All stored paths are archive-relative.
"""

from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from .files import content_hash, is_link, valid_topic_name

STATE_DIRECTORY = '.smart-research-archive'
FORMAT_VERSION = 1


def stable_key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class ArchiveStore:
    def __init__(self, folder):
        self.root = Path(folder).resolve(strict=True)
        self.directory = self.root / STATE_DIRECTORY
        if is_link(self.directory):
            raise ValueError('Der Archivspeicher darf keine Verknüpfung sein.')
        self.directory.mkdir(exist_ok=True)
        self.database = self.directory / 'archive.sqlite3'
        if is_link(self.database):
            raise ValueError('Der Archivspeicher darf keine Verknüpfung sein.')
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cache (kind TEXT, key TEXT, value TEXT, PRIMARY KEY(kind,key));
                CREATE TABLE IF NOT EXISTS decisions (path TEXT, digest TEXT, value TEXT, PRIMARY KEY(path,digest));
                CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, digest TEXT, size INTEGER, modified INTEGER);
                CREATE TABLE IF NOT EXISTS moves (id INTEGER PRIMARY KEY, source TEXT, target TEXT, digest TEXT,
                    old_metadata TEXT, new_metadata TEXT, topic TEXT, status TEXT, created REAL);
                CREATE TABLE IF NOT EXISTS corrections (id INTEGER PRIMARY KEY, digest TEXT, suggested TEXT,
                    chosen TEXT, terms TEXT, applied INTEGER DEFAULT 0);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def relative(self, path):
        path = Path(path)
        if is_link(path):
            raise ValueError('Verknüpfungen werden nicht verarbeitet.')
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise ValueError('Datei liegt außerhalb dieses Archivs.')
        return resolved.relative_to(self.root).as_posix()

    def path(self, relative):
        candidate = self.root / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or candidate.resolve() == self.root:
            raise ValueError('Ungültiger Archivpfad.')
        self.relative(candidate)
        return candidate

    def get(self, key, default=None):
        with self.connection() as db:
            row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row['value']) if row else default

    def set(self, key, value):
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value, ensure_ascii=False)))

    def profile(self):
        result = self.get('profile')
        if result is not None:
            self.validate_profile(result)
        return result

    @staticmethod
    def validate_profile(profile):
        if profile.get('format_version') != FORMAT_VERSION or profile.get('engine') not in ('local', 'llm'):
            raise ValueError('Dieses Archivprofil hat ein unbekanntes Format.')
        themes, names = profile.get('topics'), set()
        if not isinstance(themes, list) or len(themes) > 5:
            raise ValueError('Archivprofil: höchstens fünf Themen.')
        for theme in themes:
            name = theme.get('name', '')
            if (not valid_topic_name(name) or name.casefold() in names or name.casefold() == 'unclassified'
                    or not isinstance(theme.get('description'), str) or len(theme['description']) > 800
                    or not isinstance(theme.get('keywords'), list)
                    or any(not isinstance(word, str) or not word.strip() or len(word) > 200 for word in theme['keywords'])):
                raise ValueError('Das Archiv enthält ungültige Themenregeln.')
            names.add(name.casefold())

    def save_profile(self, topics, engine):
        profile = {'format_version': FORMAT_VERSION, 'engine': engine, 'topics': [
            {'name': topic.name, 'description': topic.description, 'keywords': list(topic.keywords)}
            for topic in topics if topic.included]}
        self.validate_profile(profile)
        self.set('profile', profile)
        self.set('managed_folders', sorted(set(self.get('managed_folders', []) + [t['name'] for t in profile['topics']])))
        return profile

    def cached(self, kind, key):
        with self.connection() as db:
            row = db.execute('SELECT value FROM cache WHERE kind=? AND key=?', (kind, key)).fetchone()
        return json.loads(row['value']) if row else None

    def checkpoint(self, kind, key, value):
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)', (kind, key, json.dumps(value, ensure_ascii=False)))

    def clear_cache(self):
        with self.connection() as db:
            db.execute('DELETE FROM cache')

    def decision(self, path, digest):
        with self.connection() as db:
            row = db.execute('SELECT value FROM decisions WHERE path=? AND digest=?', (self.relative(path), digest)).fetchone()
        return json.loads(row['value']) if row else None

    def save_decision(self, paper, status):
        value = {'status': status, 'metadata': asdict(paper.metadata), 'topic': paper.topic, 'reason': paper.reason}
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO decisions VALUES (?,?,?)',
                       (self.relative(paper.source), paper.fingerprint, json.dumps(value, ensure_ascii=False)))

    def index_file(self, path, digest=None):
        info = path.stat()
        digest = digest or content_hash(path)
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO files VALUES (?,?,?,?)',
                       (self.relative(path), digest, info.st_size, info.st_mtime_ns))
        return digest

    def duplicate_index(self, topics, cancelled=lambda: False):
        """Hash direct PDFs in known topic folders only; no text/model analysis."""
        result = {}
        for name in dict.fromkeys([*topics, *self.get('managed_folders', []), 'Unclassified']):
            if not valid_topic_name(name):
                continue
            folder = self.root / name
            if not folder.is_dir() or is_link(folder):
                continue
            for path in folder.iterdir():
                if cancelled():
                    return result
                if path.is_file() and path.suffix.lower() == '.pdf' and not is_link(path):
                    relative, info = self.relative(path), path.stat()
                    with self.connection() as db:
                        previous = db.execute('SELECT * FROM files WHERE path=?', (relative,)).fetchone()
                    digest = (previous['digest'] if previous and previous['size'] == info.st_size
                              and previous['modified'] == info.st_mtime_ns else self.index_file(path))
                    result.setdefault(digest, path)
        return result

    def begin_move(self, paper, target, metadata, topic):
        with self.connection() as db:
            cursor = db.execute('''INSERT INTO moves
                (source,target,digest,old_metadata,new_metadata,topic,status,created) VALUES (?,?,?,?,?,?,?,?)''',
                (self.relative(paper.source), self.relative(target), paper.fingerprint,
                 json.dumps(asdict(paper.metadata), ensure_ascii=False), json.dumps(asdict(metadata), ensure_ascii=False),
                 topic, 'prepared', time.time()))
            return cursor.lastrowid

    def mark_move(self, identifier, status):
        with self.connection() as db:
            db.execute('UPDATE moves SET status=? WHERE id=?', (status, identifier))

    def recover_moves(self):
        with self.connection() as db:
            rows = db.execute("SELECT * FROM moves WHERE status IN ('prepared','undo_pending')").fetchall()
        for row in rows:
            source, target = self.path(row['source']), self.path(row['target'])
            if row['status'] == 'prepared' and not source.exists() and target.is_file() and content_hash(target) == row['digest']:
                self.mark_move(row['id'], 'completed')
            elif row['status'] == 'undo_pending' and not target.exists() and source.is_file() and content_hash(source) == row['digest']:
                self.mark_move(row['id'], 'undone')

    def last_move(self):
        self.recover_moves()
        with self.connection() as db:
            row = db.execute("SELECT * FROM moves WHERE status='completed' ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def correction(self, paper, suggested, chosen):
        if suggested == chosen:
            return
        from .suggestions import terms_in
        text = (paper.analysis or {}).get('summary') or paper.text[:12000]
        terms = sorted(terms_in(text))[:100]
        with self.connection() as db:
            db.execute('INSERT INTO corrections (digest,suggested,chosen,terms) VALUES (?,?,?,?)',
                       (paper.fingerprint, suggested, chosen, json.dumps(terms, ensure_ascii=False)))

    def correction_suggestions(self):
        with self.connection() as db:
            rows = db.execute('SELECT * FROM corrections WHERE applied=0 ORDER BY id').fetchall()
        grouped = {}
        for row in rows:
            grouped.setdefault(row['chosen'], []).append(dict(row))
        suggestions = []
        for name, records in grouped.items():
            records = list({row['digest']: row for row in records}.values())
            if len({row['digest'] for row in records}) < 2:
                continue
            counts = {}
            for row in records:
                for term in set(json.loads(row['terms'])):
                    counts[term] = counts.get(term, 0) + 1
            terms = sorted((term for term, count in counts.items() if count >= 2),
                           key=lambda term: (-counts[term], -len(term.split()), term))[:5]
            suggestions.append({'name': name, 'keywords': terms,
                                'count': len({row['digest'] for row in records}),
                                'ids': [row['id'] for row in records]})
        return suggestions

    def resolve_corrections(self, ids):
        with self.connection() as db:
            db.executemany('UPDATE corrections SET applied=1 WHERE id=?', [(identifier,) for identifier in ids])


def existing_profile(folder):
    folder = Path(folder)
    if not (folder / STATE_DIRECTORY / 'archive.sqlite3').is_file():
        return None
    return ArchiveStore(folder).profile()
