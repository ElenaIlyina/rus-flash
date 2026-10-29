#!/usr/bin/env python3
"""Build production data and the separate local review workbench."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from card_data import load_cards
from exam_2027 import mapping
from paronym_sources import validate_sources


def read(path):return json.loads((ROOT/path).read_text())


def main():
    subprocess.run([sys.executable,str(ROOT/'scripts/build_app_data.py')],check=True)
    reviews={}
    for name in ['prefix_card_reviews','root_card_reviews','ege_1_6_card_reviews']:
        for entry in read(f'dev/data/knowledge/{name}.json')['cards']:
            if entry['id'] in reviews:raise ValueError('Duplicate review')
            reviews[entry['id']]=entry
    book=read('dev/data/knowledge/paronyms.json')
    sources=validate_sources(book,ROOT)
    pairs={p['id']:p for p in book['pairs']}
    issues=read('dev/data/knowledge/review_issues.json')['cards']
    overrides=read('dev/data/content_review_overrides.json')['cards']
    rules=read('data/knowledge/handbook.json')['paragraphs']
    editions=read('html/assets/data/handbook-sources.json')['editions']
    versions={p['id']:p['textSha256'] for edition in editions for p in edition['paragraphs']}
    cards=load_cards()
    if set(issues)-{c['number'] for c in cards}:raise ValueError('Unknown issue card')
    entries=[]
    for card in cards:
        cid=card['number'];entry=reviews.get(cid);notes=list(issues.get(cid,[]))
        if overrides.get(cid,{}).get('reason'):notes.append(overrides[cid]['reason'])
        if not entry and not notes:continue
        if entry and entry.get('authorReviewRequired') is False and not notes:continue
        linked_rules=[r for r in rules if mapping(card)['task'] in r['tasks']]
        refs={sid for row in (entry or {}).get('rows',[]) for sid in row['sourceIds']}
        refs.update(ref['sourceId'] for rule in linked_rules for ref in rule.get('sourceRefs',[]))
        basis={'card':card,'review':entry,'paronyms':{pid:pairs[pid] for pid in (entry or {}).get('paronymPairIds',[])},
               'dictionarySources':{sid:source['sha256'] for sid,source in sources.items()} if (entry or {}).get('paronymPairIds') else {},
               'rules':linked_rules,'sources':{sid:versions[sid] for sid in sorted(refs)},'issues':notes}
        version=hashlib.sha256(json.dumps(basis,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        parts=['объяснение','источники по рядам'] if entry else ['замечания к материалу']
        if entry and entry.get('hint'):parts.append('индивидуальная подсказка')
        if entry and entry.get('sourceEditApproval'):parts.append('условие (согласовано)')
        entries.append({'id':cid,'version':version,'parts':parts,'issues':notes})
    path=ROOT/'dev/review/review-data.json'
    path.write_text(json.dumps(entries,ensure_ascii=False,separators=(',',':')))
    print(f'Review workbench: {len(entries)} entries. Serve the repository root; open /dev/review/.')


if __name__=='__main__':main()
