#!/usr/bin/env python3
"""Validate fresh task-24 decisions against all five statements and passage quotations."""
import argparse
import json
import re
from review_punctuation_explanations import ROOT, frozen, digest, clean
from review_isolation_explanations import plain_question
from exam_2027 import mapping
from review_reading_content import sentences

REGISTRY = ROOT / 'dev/data/knowledge/discourse_card_reviews.json'
ISSUES = ROOT / 'dev/docs/content-audit/explanations-20-26-issues.json'


def read_registry():
    return json.loads(REGISTRY.read_text())


SOURCES = ROOT / 'dev/data/knowledge/discourse_sources.json'


def load_sources():
    catalog = json.loads(SOURCES.read_text())
    sources, book_hashes = {}, {}
    for entry in catalog['sources']:
        path = ROOT / entry['file']
        book = ROOT / entry['sourceFile']
        # The source PDF belongs to the author's materials directory. Saved page
        # evidence remains usable in a checkout without that external directory.
        if book.is_file() and book not in book_hashes:
            book_hashes[book] = digest_bytes(book.read_bytes())
        if entry['id'] in sources or digest_bytes(path.read_bytes()) != entry['snapshotSha256'] or digest(path.read_text().rstrip('\n')) != entry['textSha256'] or not re.fullmatch('[0-9a-f]{64}', entry['sourceFileSha256']) or (book in book_hashes and book_hashes[book] != entry['sourceFileSha256']):
            raise ValueError('Stale discourse source snapshot or original PDF')
        sources[entry['id']] = entry
    return {'citationLabel':catalog['citationLabel'], 'sources':sources}


def digest_bytes(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()


def referenced_numbers(statement):
    text = re.sub(r'^\s*[1-5]\)\s*', '', plain_question(statement))
    numbers = set(map(int, re.findall(r'\d+', text)))
    for first, last in re.findall(r'(\d+)\s*[–—‒−-]\s*(\d+)', text):
        numbers.update(range(int(first), int(last)+1))
    return numbers


def selection(card):
    question = plain_question(card['question']).lower()
    return 'incorrect' if any(word in question for word in ['неверн', 'ошибочн']) else 'correct'


def chosen(review, row):
    return row['isCorrect'] != (review['selection'] == 'incorrect')


def validate(card, review, sources):
    if card['number'] != review['id'] or mapping(card)['task'] != 24 or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Task-24 source changed')
    prov = review['rewriteReview']
    if review['task'] != 24 or not review.get('hint') or review['selection'] != selection(card) or prov.get('scope') != 'all_five_statements_and_referenced_context' or prov.get('oldExplanationsUsedAsEvidence') is not False or prov.get('independentTeacherAcceptance') is not False:
        raise ValueError('Invalid task-24 provenance or selection direction')
    source = review['sourceEvidence']
    if source.get('kind') != 'original_fipi_passage' or source.get('method') != 'referenced_fragments_and_adjacent_context_read' or source.get('textSha256') != digest(plain_question(card['text'])):
        raise ValueError('Stale passage evidence')
    evidence = review['theoryEvidence']
    if review.get('theoryScope') != 'general_type_criteria_not_fipi_key' or {e['sourceId'] for e in evidence} != set(sources['sources']) or len(evidence) != len(sources['sources']):
        raise ValueError('Incomplete discourse criteria evidence')
    for item in evidence:
        source = sources['sources'][item['sourceId']]
        if item['textSha256'] != source['textSha256'] or item['method'] != source['readMethod']:
            raise ValueError('Stale discourse criteria evidence')
    ss = sentences(card)
    if len(card['variants']) != 5 or len(review['rows']) != 5:
        raise ValueError('Incomplete statement coverage')
    for n, row in enumerate(review['rows'], 1):
        if row['number'] != n or row['statement'] != plain_question(card['variants'][n-1]) or type(row['isCorrect']) is not bool or not row.get('reason') or not row.get('evidence'):
            raise ValueError('Invalid statement classification')
        if not referenced_numbers(row['statement']) <= {e['sentence'] for e in row['evidence']}:
            raise ValueError('Referenced range not fully checked')
        seen = set()
        for e in row['evidence']:
            number = e['sentence']
            if type(number) is not int or not 1 <= number <= len(ss) or number in seen:
                raise ValueError('Invalid passage reference')
            seen.add(number)
            if e['quote'] != ss[number-1] or e['sentenceSha256'] != digest(ss[number-1]):
                raise ValueError('Quote differs from original passage')
    key = ''.join(str(row['number']) for row in review['rows'] if chosen(review, row))
    mask = ''.join('1' if chosen(review, row) else '0' for row in review['rows'])
    if key != card['answer'] or mask != card['answer_verify']:
        raise ValueError('Manual reading differs from preserved key or binary mask')
    pending = [i for i in json.loads(ISSUES.read_text())['issues'] if i['status'] == 'open' and i.get('affectsExplanation') and review['id'] in i['cardIds']]
    if bool(pending) != bool(review.get('sourceReviewPending')) or (pending and not review.get('sourceReviewNote')):
        raise ValueError('Pending log and task-24 explanation disagree')
    if review['status'] != ('assistant_rewritten_requires_source_review' if pending else 'assistant_rewritten_source_linked'):
        raise ValueError('Invalid task-24 review status')


def render(card, review, sources):
    validate(card, review, sources)
    direction = 'ОШИБОЧНЫЕ' if review['selection'] == 'incorrect' else 'ВЕРНЫЕ'
    blocks = [f'Нужно выбрать <b>{direction}</b> утверждения о построении текста. Ответ: <b>{card["answer"]}</b>.']
    if review.get('sourceReviewPending'):
        blocks.insert(0, '<b>Требует уточнения.</b><br>' + clean(review['sourceReviewNote']))
    for row in review['rows']:
        verdict = 'верно' if row['isCorrect'] else 'неверно'
        action = 'выбираем' if chosen(review, row) else 'не выбираем'
        evidence = '<br>'.join(f'({e["sentence"]}) «{clean(e["quote"])}»' for e in row['evidence'])
        blocks.append(f'<b>Утверждение {row["number"]} — {verdict}; {action}.</b><br>' + clean(row['statement']) + '<br>' + clean(row['reason']) + '<br>Основание — исходный текст:<br>' + evidence)
    blocks.append('Критерии анализа типов речи: ' + clean(sources['citationLabel']) + '<br>Конкретные смысловые связи установлены по приведённым фрагментам; справочник не является ключом к карточке.')
    return '<br><br>'.join(blocks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    registry = read_registry()
    sources = load_sources()
    logpath = ROOT / 'dev/docs/content-audit/explanation-reviews.json'
    log = json.loads(logpath.read_text())
    writes, ids = [], set()
    for r in registry['cards']:
        if r['id'] in ids:
            raise ValueError('Duplicate task-24 review')
        ids.add(r['id'])
        path = ROOT / f'data/card_{r["id"]}.json'
        card = json.loads(path.read_text())
        result = render(card, r, sources)
        if result == card.get('explanation', ''):
            continue
        before = digest(card.get('explanation', ''))
        if not args.write or before != r['previousExplanationSha256']:
            raise ValueError('Stale task-24 explanation')
        card['explanation'] = result
        writes.append((path, json.dumps(card, ensure_ascii=False, indent=2) + '\n'))
        log['reviews'].append({'changeId':'DISCOURSE24-' + r['id'], 'id':r['id'], 'reviewDate':r['reviewDate'], 'reviewer':'assistant', 'status':r['status'], 'reason':'Заново проверены все пять утверждений, указанные фрагменты и соседний контекст. Различены типы речи и направления смысловых связей; приведены точные цитаты и источник критериев. Старые объяснения не использовались.', 'answerUnchanged':True, 'previousExplanationSha256':before, 'explanationSha256':digest(result)})
    if writes:
        writes.append((logpath, json.dumps(log, ensure_ascii=False, indent=2) + '\n'))
        originals = {p:p.read_bytes() for p, _ in writes}
        try:
            for p, t in writes:
                p.write_text(t)
        except OSError:
            for p, t in originals.items():
                p.write_bytes(t)
            raise
    if args.report:
        allids = {c['number'] for p in (ROOT / 'data').glob('card_*.json') if mapping(c := json.loads(p.read_text()))['task'] == 24}
        report = {'task':24, 'reviewDate':registry['reviewDate'], 'taskCards':len(allids), 'freshlyReviewedCards':len(ids), 'statementsReviewed':sum(len(r['rows']) for r in registry['cards']), 'remainingCards':sorted(allids-ids), 'pendingCards':[r['id'] for r in registry['cards'] if r.get('sourceReviewPending')], 'independentTeacherAcceptance':False, 'cards':sorted(ids)}
        (ROOT / 'dev/docs/content-audit/task-24-explanations-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Task 24: {len(ids)} cards checked; {len(writes)-1 if writes else 0} explanations updated')


if __name__ == '__main__':
    main()
