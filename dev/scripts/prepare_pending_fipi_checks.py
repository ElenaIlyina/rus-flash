#!/usr/bin/env python3
"""Build a snapshot-bound pending queue from a returned FIPI report.

No network or production writes. A checked response must have HTTP 2xx,
exact body '3'/'2', and a matching response hash; row status alone is not evidence.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_fipi_answers as checker


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def prepare(report, raw_cards, plans, report_sha256):
    if report.get('status') != 'finished' or report.get('project') != checker.PROJECT:
        raise ValueError('Нужен завершённый журнал нашего проекта')
    if report.get('endpoint') != 'https://ege.fipi.ru/bank/solve.php':
        raise ValueError('Неожиданный сервер в журнале')
    proposed = {}
    for plan in plans:
        checker.validate_plan(plan)
        for check in plan['checks']:
            cid = check['cardId']
            if cid in proposed:
                raise ValueError('Повтор карточки в планах: ' + cid)
            proposed[cid] = check
    seen_ids, seen_guids = set(), set()
    pending, accepted, essays, observations = [], [], [], []
    for row in report['results']:
        cid, guid = row['cardId'], row['guid'].lower()
        if cid in seen_ids or guid in seen_guids:
            raise ValueError('Повтор карточки в журнале: ' + cid)
        seen_ids.add(cid)
        seen_guids.add(guid)
        raw = raw_cards[cid]
        if raw['guid'].lower() != guid or digest(raw) != row['sourceContentSha256']:
            raise ValueError('Исходник журнала не совпадает: ' + cid)
        successes, rejections = [], []
        for attempt in row['attempts']:
            status = attempt['status']
            if status not in {'accepted', 'rejected'}:
                raise ValueError('Техническая ошибка требует отдельного продолжения: ' + cid)
            body = '3' if status == 'accepted' else '2'
            if (not 200 <= attempt.get('httpStatus', 0) < 300 or
                    attempt.get('response') != body or
                    attempt.get('responseSha256') != hashlib.sha256(body.encode()).hexdigest()):
                raise ValueError('Непоследовательное свидетельство ответа: ' + cid)
            (successes if status == 'accepted' else rejections).append(copy.deepcopy(attempt))
        if successes:
            if row['status'] != 'accepted':
                raise ValueError('Статус карточки расходится с попытками: ' + cid)
            accepted.append({'cardId':cid,'guid':raw['guid'],
                             'sourceContentSha256':row['sourceContentSha256'],
                             'reportSha256':report_sha256,'attempts':successes,
                             'liveTextCompared':False})
            observations.extend({'cardId':cid, **a} for a in rejections)
            continue
        if row.get('reason') == 'essay_not_automatically_graded':
            essays.append(cid)
            continue
        if cid == 'D30EAB':
            # детясли: no separating sign; row 4 is not a valid selection.
            check = {'caseId':'RECHECK-D30EAB','cardId':cid,'guid':raw['guid'],
                     'sourceSnapshot':copy.deepcopy(raw),'sourceContentSha256':digest(raw),
                     'mode':'find_accepted','hypothesisBasis':'spelling_prefix_rejected_candidate',
                     'contextSource':'raw_qblock','reason':'Ряды 2 и 5; детясли пишется без разделительного знака.',
                     'candidates':[{'answer':'25','wireAnswer':checker.wire_answer(raw,'25'),
                                    'role':'corrected_hypothesis'}]}
        else:
            if cid not in proposed:
                raise ValueError('Не подготовлен кандидат: ' + cid)
            check = copy.deepcopy(proposed[cid])
            if check['sourceContentSha256'] != digest(raw) or check['guid'].lower() != guid:
                raise ValueError('План не совпадает с исходником: ' + cid)
        rejected_wires = {a['wireAnswer'] for a in rejections}
        check['candidates'] = [a for a in check['candidates'] if a['wireAnswer'] not in rejected_wires]
        if not check['candidates']:
            raise ValueError('Все кандидаты уже отвергнуты: ' + cid)
        pending.append(check)
    if seen_ids != set(raw_cards) or len(seen_ids) != report['summary']['cardsInPlan']:
        raise ValueError('Журнал не покрывает весь снимок')
    result = checker.validate_plan({'schemaVersion':1,'project':checker.PROJECT,
                                    'previousReportSha256':report_sha256,'checks':pending})
    ledger = {'schemaVersion':1,'reportSha256':report_sha256,
              'accepted':accepted,'rejectedAlternatives':observations,'essayIds':essays,
              'summary':{'cards':len(seen_ids),'acceptedCards':len(accepted),
                         'pendingCards':len(pending),'essayCards':len(essays)}}
    return result, ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--cards', type=Path, required=True)
    parser.add_argument('--plan', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    args = parser.parse_args()
    raw = {c['number']:c for c in (json.loads(p.read_text(encoding='utf-8'))
           for p in args.cards.glob('card_*.json'))}
    plan, ledger = prepare(json.loads(args.report.read_text(encoding='utf-8')), raw,
                           [checker.load_plan(p) for p in args.plan],
                           hashlib.sha256(args.report.read_bytes()).hexdigest())
    for path, value in [(args.output,plan),(args.ledger,ledger)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(ledger['summary'],ensure_ascii=False))


if __name__ == '__main__':
    main()
