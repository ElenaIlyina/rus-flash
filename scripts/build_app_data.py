#!/usr/bin/env python3
"""Build the review UI's lazy-loaded data; never modify source card JSON.

Positions follow the official FIPI 2027 DRAFT; content/format review is separate.
Run from any directory. Outputs are ignored and reproducible.
"""
import hashlib
import json
import shutil
from pathlib import Path
from generate_manifest import classify, load_cards
from exam_2027 import mapping, text
from handbook_fb2 import read_handbook, apply_errata
from paronym_sources import validate_sources, publication_ready
from paronym_inventory import inventory as paronym_inventory

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'html' / 'assets' / 'data'


def public_dictionary_ref(ref, sources):
    """Keep audit quotes and extraction metadata out of the initial UI payload."""
    source = sources[ref['dictionaryId']]
    return {**{key:ref[key] for key in ('dictionaryId', 'headword', 'pdfPage', 'entryId') if key in ref},
            'label':source.get('citationLabel', source['title'])}


def main():
    cards = load_cards()
    if not cards:
        raise SystemExit('No cards found')
    (OUT / 'cards').mkdir(parents=True, exist_ok=True)
    paronym_mapping = json.loads((ROOT / 'data/knowledge/paronym_inventory.json').read_text())
    paronym_list = paronym_inventory(cards, paronym_mapping, mapping)
    list_source = ROOT / paronym_mapping['source']['file']
    if hashlib.sha256(list_source.read_bytes()).hexdigest() != paronym_mapping['source']['sha256']:
        raise ValueError('Paronym list source checksum changed')
    (OUT / 'paronym-index.json').write_text(json.dumps({k:v for k,v in paronym_list.items() if k!='cards'}, ensure_ascii=False, separators=(',', ':')))
    shutil.copyfile(list_source, OUT / 'paronym-index-source.pdf')
    stress_list = json.loads((ROOT / 'data/knowledge/stress-list.json').read_text())
    stress_pdf = ROOT / stress_list['sourceFile']
    if hashlib.sha256(stress_pdf.read_bytes()).hexdigest() != stress_list['sourceSha256']:
        raise ValueError('Stress list source checksum changed')
    (OUT / 'stress-list.json').write_text(json.dumps(stress_list, ensure_ascii=False, separators=(',', ':')))
    shutil.copyfile(stress_pdf, OUT / 'stress-list-source.pdf')
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
    root_reviews = json.loads((ROOT / 'data/knowledge/root_card_reviews.json').read_text())['cards']
    for entry in root_reviews:
        if entry['id'] in prefix_reviews: raise ValueError('Duplicate card review: ' + entry['id'])
        prefix_reviews[entry['id']] = entry
    priority_reviews = json.loads((ROOT / 'data/knowledge/ege_1_6_card_reviews.json').read_text())['cards']
    paronym_book = json.loads((ROOT / 'data/knowledge/paronyms.json').read_text())
    paronym_sources = validate_sources(paronym_book, ROOT)
    dictionary_out = OUT / 'dictionaries'
    dictionary_out.mkdir(exist_ok=True)
    for sid, source in paronym_sources.items():
        if source.get('format') == 'mobi':
            articles = {'title':source['title'], 'entries':list(source['_articles'].values())}
            (dictionary_out / f'{sid}.json').write_text(json.dumps(articles, ensure_ascii=False, separators=(',', ':')))
        else:
            shutil.copyfile(ROOT / source['sourceFile'], dictionary_out / f'{sid}.pdf')
    paronym_pairs = paronym_book['pairs']
    paronyms = {pair['id']:pair for pair in paronym_pairs}
    if len(paronyms) != len(paronym_pairs): raise ValueError('Duplicate paronym pair ID')
    for entry in priority_reviews:
        if entry['id'] in prefix_reviews: raise ValueError('Duplicate priority review: ' + entry['id'])
        prefix_reviews[entry['id']] = entry
    for entry in prefix_reviews.values():
        for pair_id in entry.get('paronymPairIds', []):
            if pair_id not in paronyms: raise ValueError('Missing paronym pair: ' + pair_id)
        for row in entry['rows']:
            for source_id in row['sourceIds']:
                if source_id not in source_ids: raise ValueError('Missing reviewed source: ' + source_id)
    overrides = json.loads((ROOT / 'data/content_review_overrides.json').read_text())['cards']
    for c in cards:
        cid = c['number']
        source_hash = prefix_reviews.get(cid, {}).get('sourceContentSha256')
        if source_hash:
            frozen = {key:value for key,value in c.items() if key != 'explanation'}
            actual_hash = hashlib.sha256(json.dumps(frozen, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if actual_hash != source_hash:
                raise ValueError('Reviewed source changed; author approval and re-review required: ' + cid)
        if len(cid) != 6 or any(ch not in '0123456789ABCDEF' for ch in cid):
            raise ValueError(f'Invalid card ID: {cid}')
        expected_explanation = prefix_reviews.get(cid, {}).get('explanationSha256')
        if expected_explanation and hashlib.sha256(c.get('explanation','').encode()).hexdigest() != expected_explanation:
            raise ValueError('Priority explanation changed; update review record: ' + cid)
        position = mapping(c)
        task = position['task']
        dictionary_ready = task != 5 or publication_ready(prefix_reviews.get(cid, {}), paronym_sources)
        public_card = c if dictionary_ready else {**c, 'explanation': ''}
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
            'strategyHint': prefix_reviews.get(cid, {}).get('hint', '') if dictionary_ready else '',
            'explanationReviewStatus': prefix_reviews.get(cid, {}).get('status') if dictionary_ready else 'awaiting_dictionary_verification',
            'dictionarySourceRefs': [public_dictionary_ref(ref, paronym_sources) for ref in prefix_reviews.get(cid, {}).get('dictionaryReview', {}).get('sourceRefs', [])] if dictionary_ready else [],
            'paronymComparisons': [{**paronyms[pid], 'words': [{**word, 'dictionaryRefs': [public_dictionary_ref(ref, paronym_sources) for ref in word['dictionaryRefs']]} for word in paronyms[pid]['words']]} for pid in prefix_reviews.get(cid, {}).get('paronymPairIds', []) if dictionary_ready and paronyms[pid].get('reviewStatus') == 'verified'],
            'explanationSourceRefs': [{'part':row['number'], 'sourceId':sid, 'label':f"Орфография, §{sid.rsplit('-',1)[1]} · Эксмо, 2007"} for row in prefix_reviews.get(cid, {}).get('rows', []) for sid in row['sourceIds']],
            'reviewNote': review.get('reason', '' if options_complete else 'Варианты ответов неполны. Автоматическая проверка отключена до восстановления по источнику.'),
            'hasAnswer': bool(c.get('answer', '').strip()),
            'hasExplanation': bool(public_card.get('explanation', '').strip()),
            'hasPassage': bool(text(c.get('text', ''))),
        })
        (OUT / 'cards' / f'{cid}.json').write_text(
            json.dumps(public_card, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    (OUT / 'catalog.json').write_text(json.dumps({
        'schemaVersion': 1, 'classificationStatus': 'official_fipi_2027_draft',
        'classificationSource': 'docs/ege-2027-card-mapping.md',
        'learningPolicyStatus': 'experimental_not_pedagogically_validated',
        'taskNames': names, 'cards': catalog,
    }, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    issues = json.loads((ROOT / 'data/knowledge/review_issues.json').read_text())['cards']
    if set(issues) - {c['number'] for c in cards}: raise ValueError('Unknown card in review issues')
    source_versions = {p['id']:p['textSha256'] for source in source_entries for p in source['paragraphs']}
    debug = []
    for c in cards:
        cid = c['number']
        entry = prefix_reviews.get(cid)
        notes = list(issues.get(cid, []))
        if overrides.get(cid, {}).get('reason'): notes.append(overrides[cid]['reason'])
        if not entry and not notes: continue
        if entry and entry.get('authorReviewRequired') is False and not notes: continue
        task = mapping(c)['task']
        rules = [r for r in handbook['paragraphs'] if task in r['tasks']]
        refs = {sid for row in (entry or {}).get('rows', []) for sid in row['sourceIds']}
        refs.update(ref['sourceId'] for rule in rules for ref in rule.get('sourceRefs', []))
        basis = {'card':c, 'review':entry, 'paronyms': {pid:paronyms[pid] for pid in (entry or {}).get('paronymPairIds', [])}, 'dictionarySources': {sid:source['sha256'] for sid,source in paronym_sources.items()} if (entry or {}).get('paronymPairIds') else {}, 'rules':rules, 'sources':{sid:source_versions[sid] for sid in sorted(refs)}, 'issues':notes}
        version = hashlib.sha256(json.dumps(basis,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        parts = ['объяснение', 'источники по рядам'] if entry else ['замечания к материалу']
        if entry and entry.get('hint'): parts.append('индивидуальная подсказка')
        if entry and entry.get('sourceEditApproval'): parts.append('условие (согласовано)')
        debug.append({'id':cid,'version':version,'parts':parts,'issues':notes})
    (OUT / 'review-debug.json').write_text(json.dumps(debug,ensure_ascii=False,separators=(',', ':')))
    print(f'UI data: {len(catalog)} cards; source JSON unchanged')


if __name__ == '__main__':
    main()
