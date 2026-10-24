#!/usr/bin/env python3
"""Build the review UI's lazy-loaded data; never modify source card JSON.

Current task labels are legacy classifications, not verified EGE-2027 mappings.
Run from any directory. Outputs are ignored and reproducible.
"""
import json
from pathlib import Path
from generate_manifest import classify, load_cards, load_spec_names

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'html' / 'assets' / 'data'


def main():
    cards = load_cards()
    if not cards:
        raise SystemExit('No cards found')
    (OUT / 'cards').mkdir(parents=True, exist_ok=True)
    catalog = []
    names = load_spec_names()
    for c in cards:
        cid = c['number']
        if len(cid) != 6 or any(ch not in '0123456789ABCDEF' for ch in cid):
            raise ValueError(f'Invalid card ID: {cid}')
        task = classify(c)
        catalog.append({
            'id': cid, 'task': task, 'title': c['question'][:210],
            'hasAnswer': bool(c.get('answer', '').strip()),
            'hasExplanation': bool(c.get('explanation', '').strip()),
            'hasPassage': bool(c.get('text', '').strip()),
        })
        (OUT / 'cards' / f'{cid}.json').write_text(
            json.dumps(c, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    (OUT / 'catalog.json').write_text(json.dumps({
        'schemaVersion': 1, 'classificationStatus': 'legacy_unverified',
        'taskNames': names, 'cards': catalog,
    }, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'UI data: {len(catalog)} cards; source JSON unchanged')


if __name__ == '__main__':
    main()
