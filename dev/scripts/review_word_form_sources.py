#!/usr/bin/env python3
"""Validate task-7 source checks while preserving card text and progress versions."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from exam_2027 import mapping
from review_grammar_explanations import frozen, load_sources

PENDING_NOTE = 'В словаре также есть разговорное «соуса́». Разбор области допустимости требует уточнения; ответ проверяется по сохранённому ключу задания.'


def validate(card, review, sources):
    check = review['morphologySourceReview']
    if review['id'] != card['number'] or mapping(card)['task'] != 7 or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Word-form source check does not match its immutable card')
    if check.get('oldExplanationsUsedAsEvidence') is not False or check.get('independentTeacherAcceptance') is not False or check['scope'] != 'target_form_only':
        raise ValueError('Word-form source scope or provenance changed')
    part = check['part']
    if type(part) is not int or not 1 <= part <= len(card['variants']):
        raise ValueError('Word-form variant index changed')
    variant = card['variants'][part - 1]
    morphology = review['morphologyReview']
    if hashlib.sha256(variant.encode()).hexdigest() != check['variantSha256'] or variant != morphology['sourceExcerpt'] or check['answer'] != card['answer'] or check['answer'] != card['answer_verify'] or check['correctedExcerpt'] != morphology['correctedExcerpt']:
        raise ValueError('Word-form target or answer changed')
    if check['status'] not in ('source_supported', 'variant_scope_pending') or not check['reason'].strip():
        raise ValueError('Word-form source status or reason missing')
    if morphology['specialistGrammarReferencePending'] != (check['status'] == 'variant_scope_pending'):
        raise ValueError('Word-form unresolved status lost')
    evidence = check['grammarEvidence']
    if not evidence or len({e['sourceId'] for e in evidence}) != len(evidence):
        raise ValueError('Missing or duplicate word-form evidence')
    refs = []
    for entry in evidence:
        source = sources.get(entry['sourceId'])
        if source is None or source['textSha256'] != entry['textSha256'] or entry['method'] != 'section_text_read':
            raise ValueError('Word-form evidence does not match its source')
        url = source['url'] + ('#page='+str(source['pdfPage']) if source.get('format') == 'pdf' else '')
        refs.append({'part':part, 'sourceId':source['id'], 'label':source['citationLabel'], 'url':url})
    return refs


def main():
    reviews = json.loads((ROOT / 'dev/data/knowledge/task_7_card_reviews.json').read_text())['cards']
    sources = load_sources()
    checked = pending = 0
    for review in reviews:
        if 'morphologySourceReview' not in review:
            continue
        card = json.loads((ROOT / 'data' / ('card_'+review['id']+'.json')).read_text())
        validate(card, review, sources)
        checked += 1
        pending += review['morphologySourceReview']['status'] == 'variant_scope_pending'
    print(f'Word-form source checks: {checked}; supported: {checked-pending}; variant-scope pending: {pending}; card files untouched')


if __name__ == '__main__':
    main()
