#!/usr/bin/env python3
"""Build the review UI's lazy-loaded data; never modify source card JSON.

Positions follow the official FIPI 2027 DRAFT; content/format review is separate.
Run from any directory. Outputs are ignored and reproducible.
"""
import hashlib
import json
from pathlib import Path
from generate_manifest import classify, load_cards
from exam_2027 import mapping, text

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'html' / 'assets' / 'data'


def main():
    cards = load_cards()
    if not cards:
        raise SystemExit('No cards found')
    (OUT / 'cards').mkdir(parents=True, exist_ok=True)
    catalog = []
    profile = json.loads((ROOT / 'data/ege_2027_positions.json').read_text())
    names = {str(p['number']): p['name'] for p in profile['positions']}
    handbook = json.loads((ROOT / 'data/knowledge/handbook.json').read_text())
    (OUT / 'handbook.json').write_text(json.dumps(handbook, ensure_ascii=False, separators=(',', ':')))
    overrides = json.loads((ROOT / 'data/content_review_overrides.json').read_text())['cards']
    for c in cards:
        cid = c['number']
        if len(cid) != 6 or any(ch not in '0123456789ABCDEF' for ch in cid):
            raise ValueError(f'Invalid card ID: {cid}')
        position = mapping(c)
        task = position['task']
        version_basis = {'card': c, 'position': position, 'assessmentPolicy': 'responses-v1'}
        material_version = max(2, int(hashlib.sha256(json.dumps(version_basis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8], 16))
        trusted = bool(c.get('answer_verify', '').strip())
        has_context = task not in {1, 2, 3, 23, 24, 25, 26} or bool(text(c.get('text', '')))
        options_complete = not c.get('variants') or all(text(str(v)) for v in c['variants'])
        eligible = options_complete and trusted and task is not None and position['formatStatus'] != 'historical_format' and has_context
        review = overrides.get(cid, {})
        if review.get('eligibleForProgress') is False: eligible = False
        catalog.append({
            'id': cid, **position, 'legacyTask': classify(c), 'title': c['question'][:210],
            'skillId': f'task-{task}' if task else None,
            'hasVerifiedAnswer': trusted, 'eligibleForProgress': eligible,
            'materialVersion': material_version,
            'ruleIds': [p['id'] for p in handbook['paragraphs'] if task in p['tasks']],
            'ruleRefs': [{'id':p['id'], 'label':f"§{p['number']}. {p['title']}"} for p in handbook['paragraphs'] if task in p['tasks']],
            'explanationStatus': review.get('explanationStatus', 'pending_subject_review' if c.get('explanation', '').strip() else 'missing'),
            'reviewNote': review.get('reason', '' if options_complete else 'Варианты ответов неполны. Автоматическая проверка отключена до восстановления по источнику.'),
            'hasAnswer': bool(c.get('answer', '').strip()),
            'hasExplanation': bool(c.get('explanation', '').strip()),
            'hasPassage': bool(text(c.get('text', ''))),
        })
        (OUT / 'cards' / f'{cid}.json').write_text(
            json.dumps(c, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    (OUT / 'catalog.json').write_text(json.dumps({
        'schemaVersion': 1, 'classificationStatus': 'official_fipi_2027_draft',
        'classificationSource': 'docs/ege-2027-card-mapping.md',
        'learningPolicyStatus': 'experimental_not_pedagogically_validated',
        'taskNames': names, 'cards': catalog,
    }, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'UI data: {len(catalog)} cards; source JSON unchanged')


if __name__ == '__main__':
    main()
