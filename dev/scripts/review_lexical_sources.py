#!/usr/bin/env python3
"""Check task-6 sources, preserve keys and distinguish edits from unresolved claims."""
import hashlib
import json
from pathlib import Path
import re
import sys
from review_grammar_explanations import ROOT, digest, frozen, load_sources
sys.path.insert(0, str(ROOT / 'scripts'))
from exam_2027 import mapping


def load_books():
    books = {}
    for source in json.loads((ROOT / 'dev/data/knowledge/lexical_pdf_sources.json').read_text())['sources']:
        sid = source['id']
        if sid not in ('denisov-morkovkin-1983', 'rozental-stylistics-2001') or sid in books or source['file'] != f'data/knowledge/sources/lexical/{sid}.pdf':
            raise ValueError('Unknown or unsafe lexical book')
        if hashlib.sha256((ROOT / source['file']).read_bytes()).hexdigest() != source['sha256'] or not re.fullmatch('[0-9a-f]{64}', source['originalSha256']):
            raise ValueError('Lexical excerpt or provenance fingerprint changed')
        original = ROOT.parent / source['originalFile']
        if original.is_file() and hashlib.sha256(original.read_bytes()).hexdigest() != source['originalSha256']:
            raise ValueError('Available lexical original changed')
        if source['readMethod'] != 'visual_page_read' or len(source['originalPdfPages']) != source['pdfPages'] or len(source['printedPages']) != source['pdfPages']:
            raise ValueError('Lexical book locator missing')
        books[sid] = source
    return books


def validate(card, review, sources, books):
    check = review['lexicalSourceReview']
    if card['number'] != review['id'] or mapping(card)['task'] != 6 or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Lexical source check does not match immutable card')
    if check['scope'] != 'preserved_key_edit_in_original_sentence' or any(check.get(k) is not False for k in ('oldExplanationsUsedAsEvidence', 'independentTeacherAcceptance', 'answerUniquenessEstablished', 'originalUniversallyForbidden')):
        raise ValueError('Lexical scope or provenance changed')
    edit = review['lexicalEdit']
    if check['answer'] != card['answer'] or check['answer'] != card['answer_verify'] or check['editSha256'] != digest(json.dumps(edit, ensure_ascii=False, sort_keys=True)):
        raise ValueError('Lexical key or reviewed edit changed')
    if check['status'] not in ('key_edit_supported', 'contextual_edit_supported', 'context_scope_pending') or not check['reason'].strip():
        raise ValueError('Missing lexical status or reason')
    pending = check['status'] == 'context_scope_pending'
    if pending != bool(check.get('studentNote')) or pending and check['reason'] not in check['studentNote']:
        raise ValueError('Unresolved lexical claim needs an explicit student note')
    refs, seen = [], set()
    for entry in check['grammarEvidence']:
        source = sources.get(entry['sourceId'])
        if source is None or entry['sourceId'] in seen or source['textSha256'] != entry['textSha256'] or entry['method'] != 'section_text_read':
            raise ValueError('Stale, duplicate or unknown lexical evidence')
        seen.add(entry['sourceId'])
        refs.append({'part': 1, 'sourceId': source['id'], 'label': source['citationLabel'], 'url': source['url']})
    for entry in check['bookEvidence']:
        source = books.get(entry['sourceId']); page = entry['excerptPage']
        locator = (entry['sourceId'], page)
        if source is None or locator in seen or type(page) is not int or not 1 <= page <= source['pdfPages']:
            raise ValueError('Unknown, duplicate or invalid lexical book page')
        if entry['sourceSha256'] != source['sha256'] or entry['originalSha256'] != source['originalSha256'] or entry['method'] != 'visual_page_read' or source['originalPdfPages'][page - 1] != entry['originalPdfPage'] or source['printedPages'][page - 1] != entry['printedPage']:
            raise ValueError('Lexical book page does not match original')
        if not entry['quote'].strip() or digest(entry['quote']) != entry['quoteSha256'] or entry['role'] not in ('explicit_norm', 'corrected_collocation', 'context_definition', 'collocation_examples'):
            raise ValueError('Missing lexical quotation or unsupported evidence role')
        seen.add(locator)
        short = 'Розенталь, 2001' if 'rozental' in source['id'] else 'Денисов—Морковкин, 1983'
        refs.append({'part': 1, 'sourceId': source['id'], 'label': f'{short}, с. {entry["printedPage"]} · выбранные страницы', 'url': f'assets/data/lexical-sources/{source["id"]}.pdf#page={page}'})
    if not refs:
        raise ValueError('No lexical evidence')
    return refs


def main():
    sources, books = load_sources(), load_books()
    reviews = [r for r in json.loads((ROOT / 'dev/data/knowledge/ege_1_6_card_reviews.json').read_text())['cards'] if 'lexicalSourceReview' in r]
    for review in reviews:
        validate(json.loads((ROOT / f'data/card_{review["id"]}.json').read_text()), review, sources, books)
    supported = sum(r['lexicalSourceReview']['status'] != 'context_scope_pending' for r in reviews)
    report = {'reviewDate': '2026-11-11', 'cardsChecked': len(reviews), 'supportedEdits': supported, 'contextScopePending': len(reviews) - supported, 'oldExplanationsAccepted': False, 'independentTeacherAcceptance': False, 'answerUniquenessEstablished': False, 'cards': [{'id': r['id'], 'originalSentence': r['lexicalEdit']['sentence'], 'correctedSentence': r['lexicalEdit']['correctedSentence'], **r['lexicalSourceReview']} for r in reviews]}
    (ROOT / 'dev/docs/content-audit/task-6-lexical-source-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Lexical source checks: {len(reviews)}; supported edits: {supported}; context scope pending: {len(reviews)-supported}')


if __name__ == '__main__': main()
