#!/usr/bin/env python3
"""Validate editorial records and publish only the data needed by the application.

Run after preparing explanations/sources. The production build never imports this
script and never needs dev/. --check verifies that committed inputs are current.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from card_data import load_cards
from exam_2027 import mapping
from paronym_sources import validate_sources, publication_ready
from handbook_fb2 import read_handbook
from review_prefix_explanations import validate_rule_evidence
from review_grammar_explanations import load_sources as load_grammar_sources, public_refs as grammar_public_refs, render as render_grammar, PENDING_NOTE as GRAMMAR_PENDING_NOTE
from review_style_sources import validate as validate_style_sources
from review_cohesion_sources import validate as validate_cohesion_sources
from review_lexical_sources import load_books as load_lexical_books, validate as validate_lexical_sources
from review_word_form_sources import validate as validate_word_form_sources, PENDING_NOTE as WORD_FORM_PENDING_NOTE


def read(path):
    return json.loads((ROOT / path).read_text())


def payloads():
    cards = {c['number']:c for c in load_cards()}
    book = read('dev/data/knowledge/paronyms.json')
    sources = validate_sources(book, ROOT)
    pairs = {p['id']:p for p in book['pairs'] if p.get('reviewStatus') == 'verified'}
    def ref(value):
        return {key:value[key] for key in ('dictionaryId','headword','pdfPage','entryId') if key in value}
    public_pairs = [{
        'id':p['id'], 'words':[{key:w[key] for key in ('word','meaning','examples')} |
                             {'dictionaryRefs':[ref(r) for r in w['dictionaryRefs']]} for w in p['words']],
        'distinction':p['distinction'],
    } for p in pairs.values()]
    dictionaries = []
    for sid, source in sources.items():
        articles = source.get('format') == 'mobi'
        dictionaries.append({'id':sid, 'title':source['title'],
                             'citationLabel':source.get('citationLabel',source['title']),
                             'format':'articles' if articles else 'pdf',
                             'file':source['articlesFile'] if articles else source['sourceFile'],
                             'sha256':source['articlesSha256'] if articles else source['sha256'],
                             **({} if articles else {'pdfPages':source['pdfPages']})})
    support = {}
    _, rule_paragraphs = read_handbook(ROOT / "data/knowledge/sources/lopatin-2007.fb2.zip")
    rule_paragraphs = {paragraph["id"]: paragraph for paragraph in rule_paragraphs}
    stress = read('data/knowledge/stress-list.json')
    stress_entries = {(e['text'],e['sourcePage']) for g in stress['groups'] for e in g['entries']}
    for name in ('prefix_card_reviews','root_card_reviews','ege_1_6_card_reviews','task_7_card_reviews','suffix_card_reviews','verb_card_reviews','negation_card_reviews','n_card_reviews','joined_card_reviews'):
        for entry in read(f'dev/data/knowledge/{name}.json')['cards']:
            validate_rule_evidence(entry, rule_paragraphs)
            cid = entry['id']
            if cid in support or cid not in cards:
                raise ValueError('Duplicate or unknown support record: ' + cid)
            card = cards[cid]
            frozen = hashlib.sha256(json.dumps({k:v for k,v in card.items() if k!='explanation'},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            explanation = hashlib.sha256(card['explanation'].encode()).hexdigest()
            if entry.get('sourceContentSha256',frozen) != frozen or entry.get('explanationSha256',explanation) != explanation:
                raise ValueError('Content changed; update its editorial evidence: ' + cid)
            dictionary_ready = publication_ready(entry,sources) if entry.get('dictionaryReview') else False
            allowed = mapping(card)['task'] not in {5,6,7} or dictionary_ready
            stress_refs = entry.get('stressSourceRefs',[])
            for citation in stress_refs:
                listed = (citation['sourceEntry'],citation['sourcePage']) in stress_entries
                excluded = (citation['evidenceType']=='excluded_word_historical' and
                            citation['sourceEntry'] in stress['excludedWords'] and citation['sourcePage']==5)
                if not 1 <= citation['part'] <= 5 or not (listed or excluded):
                    raise ValueError('Unknown stress-list evidence: ' + cid)
            support[cid] = {'sourceContentSha256':frozen,'explanationSha256':explanation,
                            'explanationPublished':allowed,'hint':entry.get('hint','') if allowed else '',
                            'dictionaryRefs':[ref(r) for r in entry.get('dictionaryReview',{}).get('sourceRefs',[])] if allowed else [],
                            'paronymPairIds':[pid for pid in entry.get('paronymPairIds',[]) if allowed and pid in pairs],
                            **({'stressRefs':[{'part':r['part'],'page':r['sourcePage']} for r in stress_refs]} if stress_refs else {}),
                            'ruleSourceRefs':[{'part':row['number'],'sourceId':sid,
                                               'label':f"Орфография, §{sid.rsplit('-',1)[1]} · Эксмо, 2007"}
                                              for row in entry['rows'] for sid in row['sourceIds']]}
    grammar_sources = load_grammar_sources()
    lexical_books = load_lexical_books()
    for entry in read('dev/data/knowledge/ege_1_6_card_reviews.json')['cards']:
        if 'lexicalSourceReview' in entry:
            cid = entry['id']
            support[cid]['grammarSourceRefs'] = validate_lexical_sources(cards[cid], entry, grammar_sources, lexical_books)
            check = entry['lexicalSourceReview']
            if check['status'] == 'context_scope_pending':
                support[cid]['explanationNeedsSourceReview'] = True
                support[cid]['explanationReviewNote'] = check['studentNote']
    for entry in read('dev/data/knowledge/ege_1_6_card_reviews.json')['cards']:
        if 'contextSourceReview' in entry:
            support[entry['id']]['grammarSourceRefs'] = validate_cohesion_sources(cards[entry['id']], entry, grammar_sources)
    for entry in read('dev/data/knowledge/task_7_card_reviews.json')['cards']:
        if 'morphologySourceReview' not in entry:
            continue
        cid = entry['id']
        refs = validate_word_form_sources(cards[cid], entry, grammar_sources)
        if support[cid]['explanationPublished']:
            support[cid]['grammarSourceRefs'] = refs
            if entry['morphologySourceReview']['status'] == 'variant_scope_pending':
                support[cid]['explanationReviewNote'] = WORD_FORM_PENDING_NOTE
                support[cid]['explanationNeedsSourceReview'] = True
    for entry in read('dev/data/knowledge/grammar_card_reviews.json')['cards']:
        cid = entry['id']
        if cid in support or cid not in cards or mapping(cards[cid])['task'] != 8:
            raise ValueError('Duplicate or invalid grammar review: '+cid)
        card = cards[cid]
        if render_grammar(card, entry) != card['explanation']:
            raise ValueError('Grammar explanation differs from review: '+cid)
        support[cid] = {'sourceContentSha256':entry['sourceContentSha256'],
                        'explanationSha256':hashlib.sha256(card['explanation'].encode()).hexdigest(),
                        'explanationPublished':True, 'hint':entry['hint'], 'dictionaryRefs':[],
                        'paronymPairIds':[], 'ruleSourceRefs':[],
                        'grammarSourceRefs':grammar_public_refs(entry, grammar_sources),
                        **({'explanationReviewNote':GRAMMAR_PENDING_NOTE,'explanationNeedsSourceReview':True} if entry.get('sourceReviewPending') else {})}
    style_ids = set()
    for entry in read('dev/data/knowledge/style_source_reviews.json')['cards']:
        cid = entry['id']
        if cid not in support or cid in style_ids:
            raise ValueError('Missing or duplicate style support: '+cid)
        style_ids.add(cid)
        support[cid]['styleSourceRefs'] = validate_style_sources(cards[cid], entry, grammar_sources)
    profile = read('dev/data/ege_2027_positions.json')
    handbook = read('dev/data/knowledge/source_registry.json')
    edition_keys = {'id','title','authors','editor','publisher','year','isbn','archiveSha256','fb2Sha256','sourceFile','errataFile'}
    overrides = read('dev/data/content_review_overrides.json')
    return {
        'data/knowledge/lexical_sources.json':{'schemaVersion':1,'sources':[{k:v for k,v in book.items() if k in ('id','title','file','sha256','pdfPages','originalPdfPages','printedPages')} for book in lexical_books.values()]},
        'data/knowledge/card_support.json':{'schemaVersion':1,'cards':support},
        'data/knowledge/paronyms.json':{'schemaVersion':1,'pairs':public_pairs},
        'data/knowledge/dictionary_sources.json':{'schemaVersion':1,'sources':dictionaries},
        'data/knowledge/source_registry.json':{'schemaVersion':1,'editions':[{k:v for k,v in e.items() if k in edition_keys} for e in handbook['editions']]},
        'data/exam_profile.json':{'schemaVersion':1,'examYear':profile['examYear'],'sourceStatus':profile['sourceStatus'],
                                 'positions':[{k:p[k] for k in ('number','name')} for p in profile['positions']]},
        'data/assessment_policy.json':{'schemaVersion':1,'cards':{cid:{**{k:v for k,v in entry.items() if k=='eligibleForProgress'}, **({'reason':entry.get('studentMessage',entry['reason'])} if entry.get('reason') else {})} for cid,entry in overrides['cards'].items()}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    result = payloads()
    for name, value in result.items():
        path = ROOT / name
        if args.check:
            if not path.is_file() or json.loads(path.read_text()) != value:
                raise ValueError('Published application input is stale: ' + name)
        else:
            path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(('Checked' if args.check else 'Published') + f' {len(result)} production inputs; editorial records remain in dev/')


if __name__ == '__main__':
    main()
