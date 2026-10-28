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
        'js/settings.js', 'js/ui.js', 'js/learning.js', 'js/progress.js', 'js/hints.js', 'js/bank-order.js', 'js/assessment.js', 'js/adaptive.js', 'js/knowledge.js', 'js/progress-transfer.js',
        'assets/data/catalog.json', 'assets/data/handbook.json', 'assets/data/handbook-sources.json',
        'assets/brand/slovo-za-slovo-school.png',
    ]
    for relative in required:
        path = root / relative
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f'Missing or empty publication file: {relative}')
    # Check split styles too: otherwise a missing @import silently loses design.
    for path in (root / 'css').glob('*.css'):
        for imported in re.findall(r'@import\s+url\([\'"]([^\'"]+)[\'"]\)', path.read_text()):
            if not (path.parent / imported).is_file():
                raise ValueError(f'Missing stylesheet {imported} imported by {path}')
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
    book = json.loads((root / 'assets/data/handbook.json').read_text())
    rule_ids = {rule['id'] for rule in book['paragraphs']}
    if len(rule_ids) != len(book['paragraphs']):
        raise ValueError('Duplicate handbook paragraph IDs')
    for card in catalog['cards']:
        if any(rule_id not in rule_ids for rule_id in card.get('ruleIds', [])):
            raise ValueError(f'Missing rule for {card["id"]}')
    sources = json.loads((root / 'assets/data/handbook-sources.json').read_text())
    source_ids = set()
    for edition in sources['editions']:
        for paragraph in edition['paragraphs']:
            sid = paragraph['id']
            if sid in source_ids or not re.fullmatch(r'[a-z0-9-]+', sid):
                raise ValueError('Invalid or duplicate source paragraph: ' + sid)
            source_ids.add(sid)
            path = root / 'assets/data/handbook-sources' / f'{sid}.json'
            data = json.loads(path.read_text())
            if data['id'] != sid: raise ValueError('Source paragraph ID mismatch: ' + sid)
    for rule in book['paragraphs']:
        for ref in rule.get('sourceRefs', []):
            if ref['sourceId'] not in source_ids:
                raise ValueError('Missing source paragraph: ' + ref['sourceId'])
    for card in catalog['cards']:
        for ref in card.get('explanationSourceRefs', []):
            if ref['sourceId'] not in source_ids: raise ValueError('Missing explanation source for ' + card['id'])
    # Missing local ES module imports would otherwise cause a blank app on Pages.
    for path in (root / 'js').glob('*.js'):
        for imported in re.findall(r'\bfrom\s+[\'"]([^\'"]+)[\'"]', path.read_text()):
            if imported.startswith('.') and not (path.parent / imported).is_file():
                raise ValueError(f'Missing module {imported} imported by {path}')
    print(f'Pages artifact OK: {len(ids)} runtime cards and required assets')


if __name__ == '__main__':
    check(sys.argv[1] if len(sys.argv) > 1 else '_site')
