#!/usr/bin/env python3
"""Validate fresh task-20 numbered boundaries without changing FIPI inputs."""
import argparse
import json
from review_isolation_explanations import validate as numbered_validate, render as numbered_render
from review_punctuation_explanations import ROOT, digest, clean
from handbook_fb2 import read_handbook
from exam_2027 import mapping

REGISTRY = ROOT / 'dev/data/knowledge/complex_card_reviews.json'
ISSUES = ROOT / 'dev/docs/content-audit/explanations-20-26-issues.json'


def read_registry():
    return json.loads(REGISTRY.read_text())


def validate(card, review, paragraphs):
    pending = [i for i in json.loads(ISSUES.read_text())['issues']
               if i['status'] == 'open' and card['number'] in i['cardIds']]
    if bool(pending) != bool(review.get('sourceReviewPending')):
        raise ValueError('Task-20 pending flags disagree with issue log: ' + card['number'])
    if pending and (review['status'] != 'assistant_rewritten_requires_source_review' or not review.get('sourceReviewNote')):
        raise ValueError('Missing explicit pending explanation')
    return numbered_validate(card, dict(review, status='assistant_rewritten_source_linked'), paragraphs, expected_task=20)


def render(card, review, paragraphs):
    validate(card, review, paragraphs)
    result = numbered_render(card, dict(review, status='assistant_rewritten_source_linked'), paragraphs, expected_task=20)
    if review.get('sourceReviewPending'):
        result = '<b>Требует уточнения.</b><br>' + clean(review['sourceReviewNote']) + '<br><br>' + result
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write', action='store_true')
    p.add_argument('--report', action='store_true')
    args = p.parse_args()
    registry = read_registry()
    _, paragraphs = read_handbook(ROOT / 'data/knowledge/sources/lopatin-2007.fb2.zip')
    paragraphs = {p['id']:p for p in paragraphs}
    log_path = ROOT / 'dev/docs/content-audit/explanation-reviews.json'
    log = json.loads(log_path.read_text())
    updates, ids = [], set()
    for r in registry['cards']:
        cid = r['id']
        if cid in ids:
            raise ValueError('Duplicate review: ' + cid)
        ids.add(cid)
        path = ROOT / f'data/card_{cid}.json'
        card = json.loads(path.read_text())
        explanation = render(card, r, paragraphs)
        if explanation == card.get('explanation', ''):
            continue
        previous = digest(card.get('explanation', ''))
        if not args.write or previous != r['previousExplanationSha256']:
            raise ValueError('Stale or unapproved explanation: ' + cid)
        card['explanation'] = explanation
        updates.append((path, json.dumps(card, ensure_ascii=False, indent=2) + '\n'))
        log['reviews'].append({'changeId':'COMPLEX20-'+cid, 'id':cid,
            'reviewDate':r['reviewDate'], 'reviewer':'assistant', 'status':r['status'],
            'reason':'Заново разобраны все пронумерованные границы и связи: главные/придаточные части, однородные сказуемые, двойные союзы. Старые объяснения не использовались. Сомнения сохранены в explanations-20-26-issues.json.',
            'answerUnchanged':True, 'previousExplanationSha256':previous,
            'explanationSha256':digest(explanation)})
    if updates:
        updates.append((log_path, json.dumps(log, ensure_ascii=False, indent=2) + '\n'))
        originals = {p:p.read_bytes() for p,_ in updates}
        try:
            for path, content in updates:
                path.write_text(content)
        except OSError:
            for path, content in originals.items():
                path.write_bytes(content)
            raise
    if args.report:
        all_ids = {json.loads(p.read_text())['number'] for p in (ROOT/'data').glob('card_*.json')
                   if mapping(json.loads(p.read_text()))['task'] == 20}
        report = {'task':20, 'reviewDate':registry['reviewDate'], 'taskCards':len(all_ids),
            'freshlyReviewedCards':len(ids), 'positionsReviewed':sum(len(r['rows']) for r in registry['cards']),
            'remainingCards':sorted(all_ids-ids), 'pendingCards':sorted(r['id'] for r in registry['cards'] if r.get('sourceReviewPending')),
            'independentTeacherAcceptance':False, 'cards':sorted(ids)}
        (ROOT/'dev/docs/content-audit/task-20-explanations-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f'Task 20: {len(ids)} cards checked; {len(updates)-1 if updates else 0} explanations updated')


if __name__ == '__main__':
    main()
