#!/usr/bin/env python3
"""Merge snapshot-bound FIPI evidence; do not change production cards or keys."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import check_fipi_answers as checker
from prepare_pending_fipi_checks import digest


def merge(reports, snapshots):
    cards, hashes = {}, []
    for report, report_hash in reports:
        if report_hash in hashes:
            raise ValueError('Журнал уже добавлен')
        if report.get('status') != 'finished' or report.get('project') != checker.PROJECT:
            raise ValueError('Нужен завершённый журнал проекта')
        if report.get('endpoint') != 'https://ege.fipi.ru/bank/solve.php':
            raise ValueError('Неверный сервер')
        if report.get('previousReportSha256') and report['previousReportSha256'] not in hashes:
            raise ValueError('Не загружен предшествующий журнал')
        seen_ids, seen_guids = set(), set()
        accepted_in_run = 0
        for row in report['results']:
            cid, guid = row['cardId'], row['guid'].lower()
            if cid in seen_ids or guid in seen_guids:
                raise ValueError('Повтор карточки в журнале: ' + cid)
            seen_ids.add(cid)
            seen_guids.add(guid)
            raw = snapshots[cid]
            if raw['guid'].lower() != guid or digest(raw) != row['sourceContentSha256']:
                raise ValueError('Не совпал исходник: ' + cid)
            entry = cards.setdefault(cid, {'cardId':cid,'guid':raw['guid'],
                        'sourceContentSha256':digest(raw),'liveTextCompared':False,'attempts':[]})
            accepted_here = False
            for attempt in row['attempts']:
                status = attempt['status']
                if status not in {'accepted','rejected'}:
                    raise ValueError('Технический результат требует отдельного продолжения: ' + cid)
                body = '3' if status=='accepted' else '2'
                if (not 200 <= attempt.get('httpStatus',0) < 300 or attempt.get('response') != body or
                        attempt.get('responseSha256') != hashlib.sha256(body.encode()).hexdigest()):
                    raise ValueError('Несогласованное свидетельство ответа: ' + cid)
                entry['attempts'].append({**copy.deepcopy(attempt),'evidenceReportSha256':report_hash})
                accepted_here |= status == 'accepted'
            if accepted_here != (row['status']=='accepted'):
                raise ValueError('Статус расходится с попытками: ' + cid)
            accepted_in_run += accepted_here
            if row.get('reason') == 'essay_not_automatically_graded':
                entry['essay'] = True
        if len(seen_ids) != report['summary']['cardsInPlan'] or accepted_in_run != report['summary']['withAcceptedAnswer']:
            raise ValueError('Сводка не совпадает с карточками журнала')
        hashes.append(report_hash)
    for entry in cards.values():
        accepted = list(dict.fromkeys(a['wireAnswer'] for a in entry['attempts'] if a['status']=='accepted'))
        entry['acceptedWireAnswers'] = accepted
        entry['status'] = ('accepted' if accepted else 'essay_not_automatically_graded' if entry.get('essay')
                           else 'no_accepted_answer' if entry['attempts'] else 'not_checked')
    entries = sorted(cards.values(),key=lambda c:c['cardId'])
    return {'schemaVersion':1,'sourceReports':hashes,'productionChanged':False,'cards':entries,
            'summary':{'cards':len(entries),
                'acceptedCards':sum(c['status']=='accepted' for c in entries),
                'unresolvedCards':sum(c['status'] in {'not_checked','no_accepted_answer'} for c in entries),
                'essayCards':sum(c['status']=='essay_not_automatically_graded' for c in entries),
                'withMultipleAcceptedStrings':sum(len(c['acceptedWireAnswers'])>1 for c in entries)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,action='append',required=True)
    parser.add_argument('--cards',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    reports = [(json.loads(p.read_text(encoding='utf-8')),hashlib.sha256(p.read_bytes()).hexdigest()) for p in args.report]
    snapshots = {c['number']:c for c in (json.loads(p.read_text(encoding='utf-8')) for p in args.cards.glob('card_*.json'))}
    result = merge(reports,snapshots)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['summary'],ensure_ascii=False))


if __name__=='__main__':
    main()
