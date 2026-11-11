#!/usr/bin/env python3
"""Validate source-backed keyed insertions without accepting old explanations."""
import html
import json
import re
from review_grammar_explanations import ROOT, digest, frozen, load_sources
import sys
sys.path.insert(0, str(ROOT / 'scripts'))
from exam_2027 import mapping


def validate(card, review, sources):
    check = review['contextSourceReview']
    if review['id'] != card['number'] or mapping(card)['task'] != 1 or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Context check does not match immutable card')
    if check['scope'] != 'keyed_insertion_in_original_context' or any(check.get(k) is not False for k in ('oldExplanationsUsedAsEvidence', 'independentTeacherAcceptance', 'answerUniquenessEstablished')):
        raise ValueError('Context review scope or provenance changed')
    if check['questionSha256'] != digest(card['question']) or check['passageSha256'] != digest(card['text']) or check['answer'] != card['answer'] or check['answer'] != card['answer_verify']:
        raise ValueError('Context text or key changed')
    plain = html.unescape(re.sub('<[^>]*>', '', re.sub(r'(?:&lt;|<)(?:…|\.{3})(?:&gt;|>)', '[ПРОПУСК]', card['text'])))
    if plain.count('[ПРОПУСК]') != 1:
        raise ValueError('Expected one gap')
    before, after = plain.split('[ПРОПУСК]')
    before, after = before[-360:], after[:360]
    if (check['contextBefore'], check['contextAfter'], check['substitution']) != (before, after, before + card['answer'] + after):
        raise ValueError('Reviewed substitution changed')
    if check['status'] != 'source_supported' or not check['reason'].strip() or review['contextReview']['fullGrammarReferencePending'] is not False:
        raise ValueError('Incomplete contextual review')
    candidates = [line.strip() for line in card['question'].splitlines()[1:] if line.strip()]
    choices = check.get('choiceAnalysis', [])
    if candidates:
        if len(candidates) != 5 or len(choices) != 5:
            raise ValueError('Incomplete choice analysis')
        for i, (option, analysis) in enumerate(zip(candidates, choices), 1):
            if analysis['number'] != i or analysis['sourceOption'] != option or analysis['matchesHistoricalKey'] != (option.rstrip(',').casefold() == card['answer'].casefold()) or not analysis['reason'].strip():
                raise ValueError('Choice analysis does not match original options')
        if sum(c['matchesHistoricalKey'] for c in choices) != 1:
            raise ValueError('Historical choice key lost')
    elif choices:
        raise ValueError('Unexpected choice analysis')
    evidence = check['grammarEvidence']
    if not evidence or len({e['sourceId'] for e in evidence}) != len(evidence):
        raise ValueError('Missing or duplicate contextual evidence')
    refs = []
    for entry in evidence:
        source = sources.get(entry['sourceId'])
        if source is None or source['textSha256'] != entry['textSha256'] or entry['method'] != 'section_text_read':
            raise ValueError('Context evidence does not match source')
        fragment = source.get('sectionFragment')
        url = source['url'] + ('#' + fragment if fragment else '')
        refs.append({'part': 1, 'sourceId': source['id'], 'label': source['citationLabel'], 'url': url})
    return refs


def main():
    sources = load_sources()
    reviews = [r for r in json.loads((ROOT / 'dev/data/knowledge/ege_1_6_card_reviews.json').read_text())['cards'] if r['task'] == 1]
    for review in reviews:
        validate(json.loads((ROOT / 'data' / ('card_' + review['id'] + '.json')).read_text()), review, sources)
    report = {'reviewDate': '2026-11-10', 'scope': 'keyed_insertion_in_original_context', 'cardsChecked': len(reviews), 'choiceCards': sum('choiceAnalysis' in r['contextSourceReview'] for r in reviews), 'optionsChecked': sum(len(r['contextSourceReview'].get('choiceAnalysis', [])) for r in reviews), 'oldExplanationsAccepted': False, 'independentTeacherAcceptance': False, 'answerUniquenessEstablished': False, 'cards': [{'id': r['id'], **r['contextSourceReview']} for r in reviews]}
    (ROOT / 'dev/docs/content-audit/task-1-grammar-source-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f"Context source checks: {len(reviews)}; options: {report['optionsChecked']}")


if __name__ == '__main__':
    main()
