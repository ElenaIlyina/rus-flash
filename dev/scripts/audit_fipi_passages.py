#!/usr/bin/env python3
"""Bind FIPI shared texts through explicit group IDs, then audit safe formatting.

The uploaded Windows-1251 page is data; no scripts or external assets execute.
Only formatting-only text restorations are applied. Meaning changes stop the run.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from lxml import html
import audit_fipi_format as presentation

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'dev/docs/references/fipi-full-2026-10-30/source.html'
SOURCE_SHA256='8811e359262c8eb797aabc038ec4f9349f7c7501c024d5aa6134ed9e5c6c70f3'
REPORT=ROOT/'dev/docs/content-audit/full-page-passages.json'
LOG=ROOT/'dev/docs/content-audit/full-page-passage-changes.jsonl'
QBLOCKS='//div[contains(concat(" ",normalize-space(@class)," ")," qblock ")]'


def parse_page(data, expected):
    declaration=re.search(br'charset\s*=\s*["\']?([a-zA-Z0-9-]+)',data[:5000],re.I)
    if not declaration or declaration[1].lower()!=b'windows-1251':
        raise ValueError('Expected declared Windows-1251')
    decoded=data.decode('cp1251',errors='strict')
    tree=html.fromstring(decoded)
    blocks=tree.xpath(QBLOCKS)
    metadata={}
    for node in tree.xpath('//div[@id]'):
        match=re.fullmatch('i([0-9a-f]{6})',node.get('id',''),re.I)
        if match:
            cid=match[1].upper()
            if cid in metadata:raise ValueError('Repeated card metadata: '+cid)
            metadata[cid]=node
    groups=[];cards={};active=None
    for index,block in enumerate(blocks,1):
        identifier=block.get('id')
        if identifier is None:
            hints=block.xpath('./div[@name="hint"]')
            if len(hints)!=1 or 'Прочитайте текст' not in hints[0].text_content():
                raise ValueError('Anonymous block is not a reading passage')
            active={'sourceBlockOrdinal':index,'groupId':None,'cards':[],
                    'sourceMarkupSha256':hashlib.sha256(html.tostring(block,encoding='utf-8',with_tail=False)).hexdigest(),
                    'text':presentation.clean(block)}
            if '\ufffd' in active['text']:raise ValueError('Shared text contains a damaged character')
            groups.append(active)
            continue
        match=re.fullmatch('q([0-9a-f]{6})',identifier,re.I)
        if not match:raise ValueError('Unknown question block ID')
        cid=match[1].upper()
        if cid in cards or cid not in expected or cid not in metadata:
            raise ValueError('Unknown/duplicate question ID: '+cid)
        guids=block.xpath('.//input[translate(@name,"GUID","guid")="guid"]/@value')
        if not guids or {g.lower() for g in guids}!={expected[cid]['guid'].lower()}:
            raise ValueError('GUID mismatch: '+cid)
        raw={'number':cid,'guid':expected[cid]['guid'],'html':html.tostring(block,encoding='unicode',with_tail=False)}
        _,changes,issues=presentation.inspect(expected[cid],raw)
        if changes:raise ValueError('Question/options changed in full page: '+cid)
        row={'cardId':cid,'guid':expected[cid]['guid'],'questionSourceIssues':issues}
        membership=metadata[cid].xpath('.//div[@class="number-in-group"]')
        if len(membership)>1:raise ValueError('Multiple source groups for '+cid)
        if membership:
            part=re.fullmatch(r'\s*(\d+)\s*\(([0-9a-f]{6})\)\s*',membership[0].text_content(),re.I)
            if not part or active is None:raise ValueError('Unbound grouped question: '+cid)
            number,gid=int(part[1]),part[2].upper()
            if active['groupId'] not in {None,gid}:raise ValueError('Neighbouring group mismatch: '+cid)
            if number!=len(active['cards'])+1:raise ValueError('Group ordinal sequence mismatch: '+cid)
            active['groupId']=gid;active['cards'].append({'cardId':cid,'numberInGroup':number})
            row.update(groupId=gid,numberInGroup=number,passageSha256=presentation.digest(active['text']))
        else:
            active=None
            if expected[cid].get('text'):raise ValueError('Existing passage has no explicit source group: '+cid)
        cards[cid]=row
    if set(cards)!=set(expected):raise ValueError('Source/project inventories differ')
    gids=[g['groupId'] for g in groups]
    if None in gids or len(set(gids))!=len(gids):raise ValueError('Empty or repeated passage group')
    return groups,cards,decoded


def run(apply=False,check=False):
    data=SOURCE.read_bytes()
    if hashlib.sha256(data).hexdigest()!=SOURCE_SHA256:raise ValueError('Full source checksum mismatch')
    current={p.stem[5:]:json.loads(p.read_text()) for p in (ROOT/'data').glob('card_*.json')}
    groups,rows,decoded=parse_page(data,current)
    proposed={member['cardId']:group['text'] for group in groups for member in group['cards']}
    changed={cid for cid,value in proposed.items() if current[cid].get('text','')!=value}
    semantic=[cid for cid in changed if presentation.visible(current[cid].get('text',''))!=presentation.visible(proposed[cid])]
    if semantic:raise ValueError('Not a formatting-only restoration: '+', '.join(sorted(semantic)))
    entries=[]
    if check and changed:raise ValueError('Passage formatting differs: '+str(len(changed)))
    if apply:
        for cid in sorted(changed):
            card=current[cid];old=card['text'];frozen=presentation.digest({k:v for k,v in card.items() if k!='text'})
            card['text']=proposed[cid]
            if presentation.digest({k:v for k,v in card.items() if k!='text'})!=frozen:
                raise ValueError('Changed field outside text: '+cid)
            (ROOT/f'data/card_{cid}.json').write_text(json.dumps(card,ensure_ascii=False,indent=2)+'\n')
            entries.append({'event':'shared_passage_format_restored','date':'2026-10-30','cardId':cid,
                'groupId':rows[cid]['groupId'],'sourcePageSha256':SOURCE_SHA256,
                'before':old,'after':card['text'],'beforeProtectedFieldsSha256':frozen,
                'afterProtectedFieldsSha256':frozen,'visibleCharactersUnchanged':True,
                'reason':'Restore shared passage formatting from the explicit source group; words, question, options, answers and explanations unchanged.'})
        # Rebind editorial hashes with explicit provenance; subject review remains unchanged.
        start=len(entries)
        presentation.rebind_support(changed,entries,source_evidence={'sourcePageSha256':SOURCE_SHA256},
                                    correction_log=LOG.relative_to(ROOT))
        presentation.rebind_coverage(changed,entries,evidence_report=REPORT.relative_to(ROOT))
        for entry in entries[start:]:
            entry.update(sourcePageSha256=SOURCE_SHA256,correctionLog=str(LOG.relative_to(ROOT)))
        if entries:
            with LOG.open('a') as output:
                for entry in entries:output.write(json.dumps(entry,ensure_ascii=False)+'\n')
    damaged=[cid for cid,row in rows.items() if row['questionSourceIssues']]
    report={'schemaVersion':1,'sourceFile':str(SOURCE.relative_to(ROOT)),'sourceSha256':SOURCE_SHA256,
        'sourceEncoding':'windows-1251','decodeErrorsPolicy':'strict',
        'summary':{'questionCards':len(rows),'sharedTexts':len(groups),'cardsWithPassages':len(proposed),
                   'restoredFormattingCards':len(changed) if apply else 0,
                   'differingPassageCards':0 if apply else len(changed),
                   'visibleTextDifferences':len(semantic),'damagedQuestionCards':len(damaged)},
        'groups':groups,'cards':[rows[cid] for cid in sorted(rows)]}
    if not check and (not apply or changed or not REPORT.exists()):
        REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['summary'],ensure_ascii=False))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--apply',action='store_true')
    mode.add_argument('--check',action='store_true')
    args=parser.parse_args()
    run(args.apply,args.check)
