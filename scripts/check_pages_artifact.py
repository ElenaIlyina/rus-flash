#!/usr/bin/env python3
"""Fail publication if essential assets or generated cards are missing.

Standard library only. Does not contact FIPI or validate educational answers.
"""
import json
from pathlib import Path
import re
import sys


def check(root):
    root = Path(root)
    required = [
        'index.html', 'css/app.css', 'js/app.js', 'js/data.js', 'js/store.js',
        'js/services.js', 'js/progress-preview.js', 'assets/data/catalog.json',
        'assets/brand/slovo-za-slovo-school.png',
    ]
    for relative in required:
        path = root / relative
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f'Missing or empty publication file: {relative}')
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError(f'Symlinks are not allowed in Pages artifact: {path}')
        if path.name in {'.git', '.env', 'node_modules', '__pycache__'}:
            raise ValueError(f'Unexpected file/directory in public site: {path}')
    catalog = json.loads((root / 'assets/data/catalog.json').read_text())
    ids = [c['id'] for c in catalog['cards']]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Catalog is empty or contains duplicate IDs')
    for cid in ids:
        if not re.fullmatch('[0-9A-F]{6}', cid):
            raise ValueError(f'Invalid card ID: {cid}')
        path = root / 'assets/data/cards' / f'{cid}.json'
        card = json.loads(path.read_text())
        if card['number'] != cid:
            raise ValueError(f'Catalog/card mismatch: {cid}')
    # Missing local ES module imports would otherwise cause a blank app on Pages.
    for path in (root / 'js').glob('*.js'):
        for imported in re.findall(r'\bfrom\s+[\'"]([^\'"]+)[\'"]', path.read_text()):
            if imported.startswith('.') and not (path.parent / imported).is_file():
                raise ValueError(f'Missing module {imported} imported by {path}')
    print(f'Pages artifact OK: {len(ids)} runtime cards and required assets')


if __name__ == '__main__':
    check(sys.argv[1] if len(sys.argv) > 1 else '_site')
