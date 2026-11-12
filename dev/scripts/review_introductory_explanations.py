#!/usr/bin/env python3
"""Validate and publish task-18 introductory words and forms of address."""
import argparse
import json
from review_isolation_explanations import validate as validate_numbered, render as render_numbered
from review_punctuation_explanations import ROOT, digest
from handbook_fb2 import read_handbook
from exam_2027 import mapping

REGISTRY = ROOT / 'dev/data/knowledge/introductory_card_reviews.json'


def read_registry():
    return json.loads(REGISTRY.read_text())


def validate(card, review, paragraphs):
    return validate_numbered(card, review, paragraphs, expected_task=18)


def render(card, review, paragraphs):
    return render_numbered(card, review, paragraphs, expected_task=18)


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
            raise ValueError('Introductory explanation is stale or changed outside review: ' + cid)
        card['explanation'] = explanation
        writes.append((path, json.dumps(card, ensure_ascii=False, indent=2) + '\n'))
        log['reviews'].append({'changeId':'INTRODUCTORY18-' + cid, 'id':cid, 'reviewer':'assistant', 'reviewDate':review['reviewDate'], 'status':review['status'], 'reason':'Заново разобраны все пронумерованные позиции: вводные конструкции, обращения и слова, не требующие обособления. Добавлены подсказка и источники; условие и ключи сохранены.', 'answerUnchanged':True, 'previousExplanationSha256':previous, 'explanationSha256':digest(explanation)})
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
            if mapping(card)['task'] == 18:
                all_ids.add(card['number'])
        report = {'reviewDate':registry['reviewDate'], 'task':18, 'taskCards':len(all_ids), 'freshlyReviewedCards':len(ids), 'positionsReviewed':sum(len(r['rows']) for r in registry['cards']), 'remainingCards':sorted(all_ids - ids), 'preservedConditionsAndKeys':baseline['preservedConditionsAndKeys'], 'unchangedTask1To15CardsAndProgressVersions':baseline['unchangedTask1To15CardsAndProgressVersions'], 'independentTeacherAcceptance':False, 'cards':sorted(ids)}
        (ROOT / 'dev/docs/content-audit/task-18-explanations-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Punctuation task 18: {len(ids)} cards checked; updated {count}')


if __name__ == '__main__':
    main()
