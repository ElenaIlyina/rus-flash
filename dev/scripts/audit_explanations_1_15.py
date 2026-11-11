#!/usr/bin/env python3
"""Audit the complete local 1–15 batch without changing educational card data."""
import argparse
from collections import Counter
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from exam_2027 import mapping


def read(path):
    return json.loads((ROOT / path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(baseline):
    commit = subprocess.check_output(['git', 'rev-parse', baseline], cwd=ROOT, text=True).strip()
    raw = subprocess.check_output(['git', 'archive', commit, 'data'], cwd=ROOT)
    catalog = read('html/assets/data/catalog.json')['cards']
    by_id = {c['id']: c for c in catalog}
    support = read('data/knowledge/card_support.json')['cards']
    changed, stable, frozen_count = [], [], 0
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive:
            if not member.name.startswith('data/card_') or not member.name.endswith('.json'):
                continue
            old = json.load(archive.extractfile(member))
            card = read(member.name)
            require({k:v for k,v in old.items() if k != 'explanation'} == {k:v for k,v in card.items() if k != 'explanation'}, 'Changed FIPI inputs: '+card['number'])
            frozen_count += 1
            task = mapping(old)['task']
            if old['explanation'] != card['explanation']:
                require(task in range(8, 16), 'Explanation changed outside rewrite scope')
                basis = {'card':old, 'position':mapping(old), 'assessmentPolicy':'responses-v1'}
                old_version = max(2, int(hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8], 16))
                require(by_id[card['number']]['materialVersion'] != old_version, 'Rewritten material retained an old version')
                changed.append(card['number'])
            if task in range(1, 8):
                require(old == card, 'Changed task 1–7 card')
                basis = {'card':old, 'position':mapping(old), 'assessmentPolicy':'responses-v1'}
                version = max(2, int(hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8], 16))
                require(by_id[card['number']]['materialVersion'] == version, 'Progress version changed: '+card['number'])
                stable.append(card['number'])
    require((frozen_count, len(changed), len(stable)) == (2140, 572, 573), 'Unexpected batch scope')
    expected_pending = {r['id'] for r in read('dev/data/knowledge/grammar_card_reviews.json')['cards'] if r.get('sourceReviewPending')}
    for name, field, status in [('ege_1_6_card_reviews', 'lexicalSourceReview', 'context_scope_pending'), ('task_7_card_reviews', 'morphologySourceReview', 'variant_scope_pending')]:
        expected_pending.update(r['id'] for r in read(f'dev/data/knowledge/{name}.json')['cards'] if r.get(field, {}).get('status') == status)
    actual_pending = {c['id'] for c in catalog if c.get('explanationNeedsSourceReview')}
    require(expected_pending == actual_pending and len(actual_pending) == 22, 'Unresolved notes differ from editorial evidence')
    grammar_pending = {r['id'] for r in read('dev/docs/content-audit/grammar-review-pending.json')['cards']}
    require(grammar_pending == {cid for cid in actual_pending if by_id[cid]['task'] == 8}, 'Task-8 pending manifest differs')
    coverage = []
    for task in range(1, 16):
        rows = [c for c in catalog if c['task'] == task]
        for c in rows:
            cid = c['id']
            raw_card = read(f'data/card_{cid}.json')
            runtime = read(f'html/assets/data/cards/{cid}.json')
            require(raw_card == runtime, 'Runtime text differs: '+cid)
            require(c['hasExplanation'] and raw_card['explanation'].strip() and c['strategyHint'].strip(), 'Missing explanation or hint: '+cid)
            require(support[cid]['explanationPublished'], 'Explanation withheld: '+cid)
            require(any(c.get(k) for k in ('dictionarySourceRefs', 'stressSourceRefs', 'grammarSourceRefs', 'styleSourceRefs', 'explanationSourceRefs')), 'No source references: '+cid)
            if cid in actual_pending:
                require(bool(c.get('explanationReviewNote')) and not c.get('reviewNote'), 'Missing note or grading disabled by source review: '+cid)
        coverage.append({'task':task, 'cards':len(rows), 'explanations':sum(c['hasExplanation'] for c in rows), 'hints':sum(bool(c['strategyHint']) for c in rows), 'currentProgressEligible':sum(c['eligibleForProgress'] for c in rows), 'historicalFormat':sum(c['formatStatus'] == 'historical_format' for c in rows), 'sourceCoverage':{key:sum(bool(c.get(key)) for c in rows) for key in ('dictionarySourceRefs','stressSourceRefs','grammarSourceRefs','styleSourceRefs','explanationSourceRefs')}, 'unresolvedNotes':sum(c['id'] in actual_pending for c in rows)})
    return {'reviewDate':date.today().isoformat(), 'baselineCommit':commit, 'scope':'technical_consistency_and_recorded_source_limits_not_independent_teacher_acceptance', 'sourceCardsUnchangedExceptExplanations':frozen_count, 'rewrittenExplanations':len(changed), 'rewrittenMaterialVersions':len(changed), 'unchangedTask1To7CardsAndVersions':len(stable), 'cardsInScope':sum(r['cards'] for r in coverage), 'currentProgressEligible':sum(r['currentProgressEligible'] for r in coverage), 'historicalFormatCards':sum(r['historicalFormat'] for r in coverage), 'unresolvedNotes':len(actual_pending), 'pendingByTask':dict(sorted(Counter(by_id[cid]['task'] for cid in actual_pending).items())), 'pendingCardIds':sorted(actual_pending), 'coverage':coverage, 'limitations':['Словарные разночтения №4 учитываются отдельно в dev/disagreements.html и не входят в 22 пометки к объяснениям.','Наличие ссылки не означает независимой преподавательской приёмки объяснения.','572 переработанных объяснения №8–15 имеют новые materialVersion; неизменность прогресса подтверждается для 573 карточек №1–7.','177 карточек прежнего формата доступны для изучения, но не учитываются в текущем экзаменационном прогрессе.','Проверка не публикует сайт и не меняет ключи или принятые ответы.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', default='f4ca04a')
    args = parser.parse_args()
    report = audit(args.baseline)
    target = ROOT / 'dev/docs/content-audit/explanations-1-15-final-audit.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(f"PASS: {report['cardsInScope']} explanations/hints/sources; 22 explicit pending notes; 2140 preserved inputs; 573 stable task 1–7 versions")


if __name__ == '__main__':
    main()
