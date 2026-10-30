#!/usr/bin/env python3
"""Refresh the glossary inventory from reviewed stress options; keep curated groups.

A new spelling must first be assigned to a comparison group in the production
JSON. Unknown/unreviewed words are not silently dropped or assigned a stress.
Run after editing dev/data/knowledge/ege_1_6_card_reviews.json, before the build.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from card_data import load_cards
from exam_2027 import mapping, text
from stress_glossary import normalize, validate_glossary


def payloads():
    data=json.loads((ROOT/'data/knowledge/stress-glossary.json').read_text())
    old={word['id']:word for word in data['words']}
    words, options, card_ids={}, [], set()
    for card in json.loads((ROOT/'dev/data/knowledge/ege_1_6_card_reviews.json').read_text())['cards']:
        if card['task']!=4:continue
        card_ids.add(card['id'])
        for row in card['stressReview']['options']:
            wid=normalize(row['normativeForm'])
            word=words.setdefault(wid,{'id':wid,'form':row['normativeForm'],'cardIds':[]})
            if word['form']!=row['normativeForm']:
                raise ValueError('Conflicting reviewed stress: '+wid)
            word['cardIds'].append(card['id'])
            options.append({'wordId':wid,'cardId':card['id'],'part':row['number'],'evidenceType':row['evidenceType']})
    assigned={wid for part in data['parts'] for group in part['groups'] for wid in group['wordIds']}
    if set(words)!=assigned:
        raise ValueError('Review comparison groups before publishing. Unassigned: '+', '.join(sorted(set(words)-assigned))+'; obsolete: '+', '.join(sorted(assigned-set(words))))
    for wid,word in words.items():
        word['cardIds']=sorted(set(word['cardIds']))
        if old.get(wid,{}).get('context'):word['context']=old[wid]['context']
    data['words']=sorted(words.values(),key=lambda word:word['id'])
    data['wordCount'],data['cardCount']=len(words),len(card_ids)
    validate_glossary(data,load_cards(),mapping,text)
    evidence={'schemaVersion':1,'reviewDate':'2026-10-30','scope':'All variants, corrected to reviewed stress, from all 114 stress cards. Same spelling/form occurs once. Evidence types inherit the explicitly recorded source limitations.','wordCount':len(words),'optionCount':len(options),'options':options}
    return {'data/knowledge/stress-glossary.json':data,
            'dev/docs/content-audit/stress-glossary-evidence.json':evidence}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for name,value in payloads().items():
        path=ROOT/name
        if args.check:
            if json.loads(path.read_text())!=value:raise ValueError('Stale stress glossary: '+name)
        else:path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print('Checked stress glossary' if args.check else 'Refreshed stress glossary')

if __name__=='__main__':main()
