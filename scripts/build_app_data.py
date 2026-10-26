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
from handbook_fb2 import read_handbook, apply_errata

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
    source_registry = json.loads((ROOT / 'data/knowledge/source_registry.json').read_text())
    source_entries = []
    source_ids = set()
    source_out = OUT / 'handbook-sources'
    source_out.mkdir(exist_ok=True)
    for source in source_registry['editions']:
        metadata, paragraphs = read_handbook(ROOT / 'data/knowledge' / source['sourceFile'])
        if metadata['archiveSha256'] != source['archiveSha256'] or metadata['fb2Sha256'] != source['fb2Sha256']:
            raise ValueError('Handbook source checksum changed: ' + source['id'])
        if source.get('errataFile'):
            apply_errata(paragraphs, json.loads((ROOT / 'data/knowledge' / source['errataFile']).read_text())['entries'])
        source_entries.append({**source, 'paragraphs': [{k:v for k,v in p.items() if k not in {'body','notes','editorialNotes'}} for p in paragraphs]})
        for paragraph in paragraphs:
            source_ids.add(paragraph['id'])
            (source_out / f"{paragraph['id']}.json").write_text(json.dumps({**paragraph, 'edition': source}, ensure_ascii=False, separators=(',', ':')))
    (OUT / 'handbook-sources.json').write_text(json.dumps({'schemaVersion':1, 'editions':source_entries}, ensure_ascii=False, separators=(',', ':')))
    handbook = json.loads((ROOT / 'data/knowledge/handbook.json').read_text())
    for rule in handbook['paragraphs']:
        for ref in rule.get('sourceRefs', []):
            if ref['sourceId'] not in source_ids: raise ValueError('Missing source reference: ' + ref['sourceId'])
    (OUT / 'handbook.json').write_text(json.dumps(handbook, ensure_ascii=False, separators=(',', ':')))
    prefix_reviews = {r['id']:r for r in json.loads((ROOT / 'data/knowledge/prefix_card_reviews.json').read_text())['cards']}
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
            'explanationReviewStatus': prefix_reviews.get(cid, {}).get('status'),
            'explanationSourceRefs': [{'part':row['number'], 'sourceId':sid, 'label':f"Орфография, §{sid.rsplit('-',1)[1]} · Эксмо, 2007"} for row in prefix_reviews.get(cid, {}).get('rows', []) for sid in row['sourceIds']],
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
