#!/usr/bin/env python3
"""Import only answers backed by original FIPI response journals, without network."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import audit_fipi_format as formatting
import check_fipi_answers as checker
from merge_fipi_check_results import merge

ROOT=Path(__file__).resolve().parents[2]
LEDGER=ROOT/'dev/data/fipi-results/merged-ledger.json'
REPORT=ROOT/'dev/docs/content-audit/verified-answer-import.json'
LOG=ROOT/'dev/docs/content-audit/verified-answer-import.jsonl'
ANSWER_FIELDS={'answer','answer_verify','accepted_answers'}


def prepare(cards,ledger,snapshots):
    rows={row['cardId']:row for row in ledger['cards']}
    if set(cards)!=set(rows) or set(cards)!=set(snapshots):raise ValueError('Source/card inventories differ')
    updates={};proofs=[]
    for cid,card in sorted(cards.items()):
        row,raw=rows[cid],snapshots[cid]
        if row['guid'].lower()!=card['guid'].lower() or row['sourceContentSha256']!=formatting.digest(raw):
            raise ValueError('Answer identity/source mismatch: '+cid)
        _,changes,issues=formatting.inspect(card,raw)
        if changes:raise ValueError('Question/options differ from source: '+cid)
        if issues and not card.get('content_issue'):raise ValueError('Unmarked damaged source: '+cid)
        if row['status']=='essay_not_automatically_graded':continue
        if row['status']!='accepted':raise ValueError('No confirmed answer: '+cid)
        accepted={}
        evidence={}
        for attempt in row['attempts']:
            if attempt['status']!='accepted':continue
            wire=attempt['wireAnswer']
            if checker.wire_answer(raw,attempt['answer'])!=wire:
                raise ValueError('Candidate/wire encoding mismatch: '+cid)
            accepted.setdefault(wire,attempt['answer'])
            evidence.setdefault(wire,[])
            if attempt['evidenceReportSha256'] not in evidence[wire]:evidence[wire].append(attempt['evidenceReportSha256'])
        if list(accepted)!=row['acceptedWireAnswers']:raise ValueError('Accepted answer list mismatch: '+cid)
        primary=card.get('answer','').strip()
        if primary:
            wire=checker.wire_answer(raw,primary)
            if wire not in accepted:raise ValueError('Existing nonempty key needs subject review: '+cid)
        else:
            wire=next(iter(accepted));primary=accepted[wire]
        alternatives=[primary]+[answer for payload,answer in accepted.items() if payload!=wire]
        fields={'answer':primary,'answer_verify':wire}
        if len(alternatives)>1:fields['accepted_answers']=alternatives
        if any(card.get(k)!=v for k,v in fields.items()) or ('accepted_answers' in card and len(alternatives)==1):
            updates[cid]=fields
        proofs.append({'cardId':cid,'guid':card['guid'],'sourceContentSha256':row['sourceContentSha256'],
                       'answer':primary,'answerVerify':wire,'acceptedAnswers':alternatives,
                       'evidenceReports':evidence})
    return updates,proofs


def run(apply=False,check=False):
    ledger=json.loads(LEDGER.read_text());snapshots=formatting.snapshots()
    available={}
    for path in (ROOT/'dev/data/fipi-results').glob('*/report.json'):
        data=path.read_bytes();available[hashlib.sha256(data).hexdigest()]=json.loads(data)
    reconstructed=merge([(available[h],h) for h in ledger['sourceReports']],snapshots)
    if reconstructed!=ledger:raise ValueError('Ledger does not match original server evidence')
    cards={p.stem[5:]:json.loads(p.read_text()) for p in (ROOT/'data').glob('card_*.json')}
    updates,proofs=prepare(cards,ledger,snapshots)
    if check and updates:raise ValueError('Verified keys not published: '+str(len(updates)))
    entries=[];new=0;verification=0
    if apply:
        for cid,fields in updates.items():
            card=cards[cid];before={k:copy.deepcopy(card[k]) for k in ANSWER_FIELDS if k in card}
            protected=formatting.digest({k:v for k,v in card.items() if k not in ANSWER_FIELDS})
            new+=not bool(card.get('answer','').strip())
            verification+=bool(card.get('answer_verify')) and card['answer_verify']!=fields['answer_verify']
            card.update(fields)
            if 'accepted_answers' not in fields:card.pop('accepted_answers',None)
            if formatting.digest({k:v for k,v in card.items() if k not in ANSWER_FIELDS})!=protected:
                raise ValueError('Changed source/explanation: '+cid)
            (ROOT/f'data/card_{cid}.json').write_text(json.dumps(card,ensure_ascii=False,indent=2)+'\n')
            entries.append({'event':'verified_answer_imported','date':'2026-10-30','cardId':cid,
                'before':before,'after':fields,'beforeProtectedFieldsSha256':protected,
                'afterProtectedFieldsSha256':protected,'evidenceLedgerSha256':hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
                'reason':'Publish answers accepted by FIPI; preserve any previously confirmed primary key.'})
        formatting.rebind_support(set(updates),entries,
            source_evidence={'answerEvidenceLedgerSha256':hashlib.sha256(LEDGER.read_bytes()).hexdigest()},
            correction_log=LOG.relative_to(ROOT))
        formatting.rebind_coverage(set(updates),entries,evidence_report=REPORT.relative_to(ROOT))
        if entries:
            with LOG.open('a') as output:
                for entry in entries:output.write(json.dumps(entry,ensure_ascii=False)+'\n')
    report={'schemaVersion':1,'evidenceLedgerSha256':hashlib.sha256(LEDGER.read_bytes()).hexdigest(),
            'summary':{'confirmedCards':len(proofs),'essayCards':len(cards)-len(proofs),
                       'changedCards':len(updates) if apply else 0,'newPrimaryKeys':new,
                       'existingVerificationPayloadUpdates':verification,
                       'cardsWithConfirmedAlternatives':sum(len(p['acceptedAnswers'])>1 for p in proofs),
                       'unpublishedKeys':0 if apply else len(updates)},'cards':proofs}
    if not check and (not apply or updates or not REPORT.exists()):
        REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['summary'],ensure_ascii=False))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--apply',action='store_true')
    mode.add_argument('--check',action='store_true')
    args=parser.parse_args();run(args.apply,args.check)
