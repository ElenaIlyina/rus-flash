#!/usr/bin/env python3
"""Build the static application from published data, using the standard library.

No network, dev/ files, editorial history or development dependencies are needed.
Only the ignored html/assets/data/ output is replaced.
"""
import hashlib
import json
import shutil
from pathlib import Path
from card_data import load_cards
from exam_2027 import mapping, text
from handbook_fb2 import read_handbook, apply_errata
from dictionary_data import load_sources, public_ref
from paronym_inventory import inventory as paronym_inventory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'html/assets/data'


def read(path):
    return json.loads((ROOT/path).read_text())


def write(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')))


def main():
    cards = load_cards()
    if not cards:
        raise ValueError('No source cards found')
    support = read('data/knowledge/card_support.json')['cards']
    sources = load_sources(ROOT,read('data/knowledge/dictionary_sources.json'))
    book = read('data/knowledge/paronyms.json')
    pairs = {p['id']:p for p in book['pairs']}
    if len(pairs)!=len(book['pairs']):
        raise ValueError('Duplicate paronym comparison')
    for pair in pairs.values():
        if len(pair['words'])<2:
            raise ValueError('Paronym comparison needs two or more words')
        for word in pair['words']:
            if not word['dictionaryRefs']:
                raise ValueError('Missing dictionary reference')
            for ref in word['dictionaryRefs']:
                public_ref(ref,sources)
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT/'cards').mkdir(parents=True)
    for name, source_name, output_name in [
        ('stress-list','sourceFile','stress-list-source.pdf'),
        ('paronym_inventory',None,'paronym-index-source.pdf'),
    ]:
        data = read(f'data/knowledge/{name}.json')
        if name=='stress-list':
            source_file, digest = data[source_name],data['sourceSha256']
            write(OUT/'stress-list.json',data)
        else:
            source_file,digest = data['source']['file'],data['source']['sha256']
            index = paronym_inventory(cards,data,mapping)
            write(OUT/'paronym-index.json',{k:v for k,v in index.items() if k!='cards'})
        source = ROOT/source_file
        if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
            raise ValueError('Word-list source checksum mismatch')
        shutil.copyfile(source,OUT/output_name)
    dictionary_out = OUT/'dictionaries'
    dictionary_out.mkdir()
    for sid,source in sources.items():
        if source['format']=='articles':
            write(dictionary_out/f'{sid}.json',{'title':source['title'],'entries':source['_entries']})
        else:
            shutil.copyfile(ROOT/source['file'],dictionary_out/f'{sid}.pdf')
    source_out = OUT/'handbook-sources'
    source_out.mkdir()
    source_entries,source_ids = [],set()
    for edition in read('data/knowledge/source_registry.json')['editions']:
        metadata, paragraphs = read_handbook(ROOT/'data/knowledge'/edition['sourceFile'])
        if metadata['archiveSha256']!=edition['archiveSha256'] or metadata['fb2Sha256']!=edition['fb2Sha256']:
            raise ValueError('Handbook source checksum mismatch')
        if edition.get('errataFile'):
            apply_errata(paragraphs,read('data/knowledge/'+edition['errataFile'])['entries'])
        source_entries.append({**edition,'paragraphs':[{k:v for k,v in p.items() if k not in {'body','notes','editorialNotes'}} for p in paragraphs]})
        for paragraph in paragraphs:
            source_ids.add(paragraph['id'])
            write(source_out/f"{paragraph['id']}.json",{**paragraph,'edition':edition})
    write(OUT/'handbook-sources.json',{'schemaVersion':1,'editions':source_entries})
    handbook = read('data/knowledge/handbook.json')
    for rule in handbook['paragraphs']:
        if any(r['sourceId'] not in source_ids for r in rule.get('sourceRefs',[])):
            raise ValueError('Missing handbook paragraph')
    write(OUT/'handbook.json',handbook)
    policy = read('data/assessment_policy.json')['cards']
    names = {str(p['number']):p['name'] for p in read('data/exam_profile.json')['positions']}
    catalog = []
    for card in cards:
        cid = card['number']
        if not re_id(cid):
            raise ValueError('Invalid card ID: '+cid)
        entry = support.get(cid,{})
        if entry:
            frozen = {k:v for k,v in card.items() if k!='explanation'}
            digest = hashlib.sha256(json.dumps(frozen,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            if digest!=entry['sourceContentSha256'] or hashlib.sha256(card['explanation'].encode()).hexdigest()!=entry['explanationSha256']:
                raise ValueError('Published card/support data disagree: '+cid)
        position = mapping(card)
        task = position['task']
        allowed = task not in {5,6,7} or entry.get('explanationPublished',False)
        public_card = card if allowed else {**card,'explanation':''}
        basis = {'card':card,'position':position,'assessmentPolicy':'responses-v1'}
        version = max(2,int(hashlib.sha256(json.dumps(basis,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:8],16))
        trusted = bool(card.get('answer_verify','').strip())
        context = task not in {1,2,3,23,24,25,26} or bool(text(card.get('text','')))
        complete = not card.get('variants') or all(text(str(v)) for v in card['variants'])
        active_policy = policy.get(cid,{})
        eligible = complete and trusted and task is not None and position['formatStatus']!='historical_format' and context
        if active_policy.get('eligibleForProgress') is False:
            eligible = False
        refs = entry.get('ruleSourceRefs',[])
        if any(r['sourceId'] not in source_ids for r in refs):
            raise ValueError('Missing rule source for '+cid)
        comparisons = []
        for pid in entry.get('paronymPairIds',[]) if allowed else []:
            pair = pairs[pid]
            comparisons.append({**pair,'words':[{**word,'dictionaryRefs':[public_ref(r,sources) for r in word['dictionaryRefs']]} for word in pair['words']]})
        catalog.append({
            'id':cid,**position,'title':card['question'][:210],
            'skillId':f'task-{task}' if task else None,'hasVerifiedAnswer':trusted,
            'eligibleForProgress':eligible,'materialVersion':version,
            'ruleIds':[p['id'] for p in handbook['paragraphs'] if task in p['tasks']],
            'ruleRefs':[{'id':p['id'],'label':f"§{p['number']}. {p['title']}"} for p in handbook['paragraphs'] if task in p['tasks']],
            'strategyHint':entry.get('hint','') if allowed else '',
            'dictionarySourceRefs':[public_ref(r,sources) for r in entry.get('dictionaryRefs',[])] if allowed else [],
            'paronymComparisons':comparisons,'explanationSourceRefs':refs,
            'reviewNote':active_policy.get('reason','' if complete else 'Варианты ответов неполны. Автоматическая проверка отключена до восстановления по источнику.'),
            'hasAnswer':bool(card.get('answer','').strip()),'hasExplanation':bool(public_card.get('explanation','').strip()),
            'hasPassage':bool(text(card.get('text',''))),
        })
        write(OUT/'cards'/f'{cid}.json',public_card)
    write(OUT/'catalog.json',{'schemaVersion':1,'classificationStatus':'official_fipi_2027_draft','taskNames':names,'cards':catalog})
    print(f'Application data: {len(catalog)} cards; production inputs only')


def re_id(value):
    return len(value)==6 and all(c in '0123456789ABCDEF' for c in value)


if __name__=='__main__':
    main()
