"""Small per-user preferences, kept separately from archive data and credentials."""

import json
import os
from pathlib import Path

PREFERENCES = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local' / 'share'))) / 'SmartResearchArchive' / 'preferences.json'


def last_folder():
    try:
        folder = Path(json.loads(PREFERENCES.read_text(encoding='utf-8')).get('last_folder', ''))
        if folder.is_dir() and str(folder) != '.':
            return str(folder)
    except (OSError, ValueError, TypeError):
        pass
    return str(Path.home() / 'Downloads')


def remember_folder(folder):
    PREFERENCES.parent.mkdir(parents=True, exist_ok=True)
    temporary = PREFERENCES.with_suffix('.tmp')
    temporary.write_text(json.dumps({'last_folder': str(folder)}, ensure_ascii=False), encoding='utf-8')
    temporary.replace(PREFERENCES)
