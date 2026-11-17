#!/usr/bin/env python3
"""Validate fresh task-23 decisions against all five statements and passage quotations."""
import argparse
import json
import re
from review_punctuation_explanations import ROOT, frozen, digest, clean
from review_isolation_explanations import plain_question
from exam_2027 import mapping

REGISTRY = ROOT / 'dev/data/knowledge/reading_content_card_reviews.json'
ISSUES = ROOT / 'dev/docs/content-audit/explanations-20-26-issues.json'


def read_registry():
    return json.loads(REGISTRY.read_text())


def sentences(card):
    text = plain_question(card['text'])
    # TASK23-SRC-002: recognize the visible number, without editing the source card.
    if card['number'] in {'8BD010', '71FF7C', 'A974B4', 'C590CF', 'CB7468'}:
        marker = '(40Минут через пятнадцать'
        if text.count(marker) != 1:
            raise ValueError('Documented malformed marker changed')
        text = text.replace(marker, '(40)Минут через пятнадцать', 1)
    markers = list(re.finditer(r'\((\d+)\)', text))
    if not markers or [int(m[1]) for m in markers] != list(range(1, len(markers)+1)):
        raise ValueError('Missing or duplicated passage sentence')
    return [text[m.end():markers[i+1].start() if i+1 < len(markers) else len(text)].strip() for i, m in enumerate(markers)]


def selection(card):
    return 'not_corresponding' if 'не соответствуют' in plain_question(card['question']).lower() else 'corresponding'


def chosen(review, row):
    return row['correspondsToText'] != (review['selection'] == 'not_corresponding')


def validate(card, review):
    if card['number'] != review['id'] or mapping(card)['task'] != 23 or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Task-23 source changed')
    prov = review['rewriteReview']
    if review['task'] != 23 or not review.get('hint') or review['selection'] != selection(card) or prov.get('scope') != 'all_five_statements_against_original_passage' or prov.get('oldExplanationsUsedAsEvidence') is not False or prov.get('independentTeacherAcceptance') is not False:
        raise ValueError('Invalid task-23 provenance or selection direction')
    source = review['sourceEvidence']
    if source.get('kind') != 'original_fipi_passage' or source.get('method') != 'full_passage_and_all_statements_read' or source.get('textSha256') != digest(plain_question(card['text'])):
        raise ValueError('Stale passage evidence')
    ss = sentences(card)
    if len(card['variants']) != 5 or len(review['rows']) != 5:
        raise ValueError('Incomplete statement coverage')
    for n, row in enumerate(review['rows'], 1):
        if row['number'] != n or row['statement'] != plain_question(card['variants'][n-1]) or type(row['correspondsToText']) is not bool or not row.get('reason') or not row.get('evidence'):
            raise ValueError('Invalid statement classification')
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
        raise ValueError('Pending log and task-23 explanation disagree')
    if review['status'] != ('assistant_rewritten_requires_source_review' if pending else 'assistant_rewritten_source_linked'):
        raise ValueError('Invalid task-23 review status')


def render(card, review):
    validate(card, review)
    direction = 'НЕ соответствующие' if review['selection'] == 'not_corresponding' else 'соответствующие'
    blocks = [f'Нужно выбрать <b>{direction}</b> тексту утверждения. Ответ: <b>{card["answer"]}</b>.']
    if review.get('sourceReviewPending'):
        blocks.insert(0, '<b>Требует уточнения.</b><br>' + clean(review['sourceReviewNote']))
    for row in review['rows']:
        verdict = 'соответствует тексту' if row['correspondsToText'] else 'не соответствует тексту'
        action = 'выбираем' if chosen(review, row) else 'не выбираем'
        evidence = '<br>'.join(f'({e["sentence"]}) «{clean(e["quote"])}»' for e in row['evidence'])
        blocks.append(f'<b>Утверждение {row["number"]} — {verdict}; {action}.</b><br>' + clean(row['statement']) + '<br>' + clean(row['reason']) + '<br>Основание — исходный текст:<br>' + evidence)
    return '<br><br>'.join(blocks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    registry = read_registry()
    logpath = ROOT / 'dev/docs/content-audit/explanation-reviews.json'
    log = json.loads(logpath.read_text())
    writes, ids = [], set()
    for r in registry['cards']:
        if r['id'] in ids:
            raise ValueError('Duplicate task-23 review')
        ids.add(r['id'])
        path = ROOT / f'data/card_{r["id"]}.json'
        card = json.loads(path.read_text())
        result = render(card, r)
        if result == card.get('explanation', ''):
            continue
        before = digest(card.get('explanation', ''))
        if not args.write or before != r['previousExplanationSha256']:
            raise ValueError('Stale task-23 explanation')
        card['explanation'] = result
        writes.append((path, json.dumps(card, ensure_ascii=False, indent=2) + '\n'))
        log['reviews'].append({'changeId':'READING23-' + r['id'], 'id':r['id'], 'reviewDate':r['reviewDate'], 'reviewer':'assistant', 'status':r['status'], 'reason':'Заново прочитан исходный текст и проверены все пять утверждений. Для каждого приведены точные пронумерованные цитаты; учтена формулировка соответствуют/не соответствуют. Старые объяснения не использовались.', 'answerUnchanged':True, 'previousExplanationSha256':before, 'explanationSha256':digest(result)})
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
        allids = {c['number'] for p in (ROOT / 'data').glob('card_*.json') if mapping(c := json.loads(p.read_text()))['task'] == 23}
        report = {'task':23, 'reviewDate':registry['reviewDate'], 'taskCards':len(allids), 'freshlyReviewedCards':len(ids), 'statementsReviewed':sum(len(r['rows']) for r in registry['cards']), 'remainingCards':sorted(allids-ids), 'pendingCards':[r['id'] for r in registry['cards'] if r.get('sourceReviewPending')], 'independentTeacherAcceptance':False, 'cards':sorted(ids)}
        (ROOT / 'dev/docs/content-audit/task-23-explanations-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Task 23: {len(ids)} cards checked; {len(writes)-1 if writes else 0} explanations updated')


if __name__ == '__main__':
    main()
