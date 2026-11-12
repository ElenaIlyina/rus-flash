#!/usr/bin/env python3
"""Validate and publish source-linked task-17 reviews at every numbered boundary."""
import argparse
from html.parser import HTMLParser
import json
import re
from review_punctuation_explanations import ROOT, clean, digest, frozen
from handbook_fb2 import read_handbook
from exam_2027 import mapping

REGISTRY = ROOT / 'dev/data/knowledge/isolation_card_reviews.json'


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_question(question):
    parser = PlainText()
    parser.feed(question)
    return re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()


def read_registry():
    return json.loads(REGISTRY.read_text())


def validate(card, review, paragraphs, expected_task=17):
    if card['number'] != review['id'] or mapping(card)['task'] != expected_task or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Isolation review does not match original card')
    if review['task'] != expected_task or review['status'] != 'assistant_rewritten_source_linked' or not review['hint'].strip() or not review['structure'].strip():
        raise ValueError('Incomplete isolation review')
    provenance = review['rewriteReview']
    if provenance['scope'] != 'all_numbered_positions' or any(provenance.get(k) is not False for k in ('oldExplanationsUsedAsEvidence', 'independentTeacherAcceptance', 'answerUniquenessEstablished')):
        raise ValueError('Invalid isolation provenance')
    sentence = review['markedSentence']
    question = plain_question(card['question'])
    prefix = question[:-len(sentence)].strip() if sentence else ''
    if not re.search(r'(?:запятая\(-ые\)|запятые)\.$', prefix) or not question.endswith(sentence) or not re.search(r'\([1-9]\)', sentence):
        raise ValueError('Marked sentence differs from original question')
    numbers = [int(n) for n in re.findall(r'\(([1-9])\)', sentence)]
    if numbers != list(range(1, len(numbers) + 1)) or len(review['rows']) != len(numbers):
        raise ValueError('Missing or duplicate numbered position')
    selected = []
    for n, row in zip(numbers, review['rows']):
        if row['number'] != n or type(row['comma']) is not bool or not row['reason'].strip() or not row['sourceIds'] or len(set(row['sourceIds'])) != len(row['sourceIds']):
            raise ValueError('Invalid numbered position')
        if row['comma']:
            selected.append(str(n))
    key = ''.join(selected)
    if not key or key != card['answer'] or key != card['answer_verify']:
        raise ValueError('Isolation punctuation differs from preserved keys')
    required = {sid for row in review['rows'] for sid in row['sourceIds']}
    evidence = review['paragraphEvidence']
    if len(evidence) != len(required) or {e['sourceId'] for e in evidence} != required:
        raise ValueError('Incomplete isolation rule evidence')
    for item in evidence:
        p = paragraphs.get(item['sourceId'])
        if not p or p['part'] != 'punctuation' or p['textSha256'] != item['textSha256'] or item['method'] != 'paragraph_text_read':
            raise ValueError('Stale isolation source evidence')
    chosen = set(selected)
    return re.sub(r'\s*\(([1-9])\)\s*', lambda m: ', ' if m[1] in chosen else ' ', sentence).strip()


def render(card, review, paragraphs, expected_task=17):
    corrected = validate(card, review, paragraphs, expected_task)
    blocks = [f'Ответ: <b>{card["answer"]}</b>.', clean(review['structure'])]
    for row in review['rows']:
        verdict = 'нужна запятая' if row['comma'] else 'запятая не нужна'
        blocks.append(f'<b>Позиция {row["number"]} — {verdict}.</b><br>{clean(row["reason"])}')
    blocks.append('Правильно: ' + clean(corrected))
    return '<br><br>'.join(blocks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    registry = read_registry()
    _, ps = read_handbook(ROOT / 'data/knowledge/sources/lopatin-2007.fb2.zip')
    ps = {p['id']:p for p in ps}
    log_path = ROOT / 'dev/docs/content-audit/explanation-reviews.json'
    log = json.loads(log_path.read_text())
    writes, ids = [], set()
    for review in registry['cards']:
        cid = review['id']
        if cid in ids:
            raise ValueError('Duplicate isolation card')
        ids.add(cid)
        path = ROOT / f'data/card_{cid}.json'
        card = json.loads(path.read_text())
        explanation = render(card, review, ps)
        if card.get('explanation', '') == explanation:
            continue
        previous = digest(card.get('explanation', ''))
        if not args.write or previous != review['previousExplanationSha256']:
            raise ValueError('Isolation explanation is stale or changed outside review: ' + cid)
        card['explanation'] = explanation
        writes.append((path, json.dumps(card, ensure_ascii=False, indent=2) + '\n'))
        log['reviews'].append({'changeId':'ISOLATION17-' + cid, 'id':cid, 'reviewer':'assistant', 'reviewDate':review['reviewDate'], 'status':review['status'], 'reason':'Заново разобраны все пронумерованные позиции, границы оборотов и их связи. Добавлены подсказка и источники; условие и ключи сохранены.', 'answerUnchanged':True, 'previousExplanationSha256':previous, 'explanationSha256':digest(explanation)})
    count = len(writes)
    if writes:
        writes.append((log_path, json.dumps(log, ensure_ascii=False, indent=2) + '\n'))
        snapshots = {p:p.read_bytes() for p, _ in writes}
        try:
            for p, content in writes:
                p.write_text(content)
        except OSError:
            for p, content in snapshots.items():
                p.write_bytes(content)
            raise
    if args.report:
        from review_punctuation_explanations import coverage_report, read_registry as read_task16, external_sources
        task16 = read_task16()
        baseline = coverage_report(task16, ps, external_sources(task16))
        all_ids = set()
        for p in (ROOT / 'data').glob('card_*.json'):
            card = json.loads(p.read_text())
            if mapping(card)['task'] == 17:
                all_ids.add(card['number'])
        report = {'reviewDate':registry['reviewDate'], 'task':17, 'taskCards':len(all_ids), 'freshlyReviewedCards':len(ids), 'positionsReviewed':sum(len(r['rows']) for r in registry['cards']), 'remainingCards':sorted(all_ids - ids), 'preservedConditionsAndKeys':baseline['preservedConditionsAndKeys'], 'unchangedTask1To15CardsAndProgressVersions':baseline['unchangedTask1To15CardsAndProgressVersions'], 'independentTeacherAcceptance':False, 'cards':sorted(ids)}
        (ROOT / 'dev/docs/content-audit/task-17-explanations-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Punctuation task 17: {len(ids)} cards checked; updated {count}')


if __name__ == '__main__':
    main()
