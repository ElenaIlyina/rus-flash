#!/usr/bin/env python3
"""Validate task-21 rule classification for every original numbered sentence."""
import argparse
import json
import re
from review_punctuation_explanations import ROOT, frozen, digest, clean
from review_isolation_explanations import plain_question
from handbook_fb2 import read_handbook
from exam_2027 import mapping

REGISTRY = ROOT/'dev/data/knowledge/punctuation_analysis_card_reviews.json'
ISSUES = ROOT/'dev/docs/content-audit/explanations-20-26-issues.json'


def read_registry():
    return json.loads(REGISTRY.read_text())


def sentences(card):
    q=plain_question(card['question'])
    markers=list(re.finditer(r'\(([1-9])\)',q))
    if [int(m[1]) for m in markers] != list(range(1,len(markers)+1)):
        raise ValueError('Missing numbered sentence')
    return [q[m.end():markers[i+1].start() if i+1<len(markers) else len(q)].strip() for i,m in enumerate(markers)]


def validate(card, review, paragraphs):
    if card['number']!=review['id'] or mapping(card)['task']!=21 or frozen(card)!=review['sourceContentSha256']:
        raise ValueError('Task-21 source changed')
    if review['task']!=21 or not review.get('hint') or not review.get('commonRule') or review['target'] not in ['тире','двоеточие','запятая']:
        raise ValueError('Incomplete task-21 review')
    if review['target'] not in plain_question(card['question']).split('(1)')[0]:
        raise ValueError('Wrong punctuation target')
    prov=review['rewriteReview']
    if prov.get('scope')!='all_numbered_sentences' or prov.get('oldExplanationsUsedAsEvidence') is not False or prov.get('independentTeacherAcceptance') is not False:
        raise ValueError('Invalid task-21 provenance')
    ss=sentences(card)
    if len(ss)!=len(review['rows']):
        raise ValueError('Incomplete sentence coverage')
    chosen=[]
    for n,(s,r) in enumerate(zip(ss,review['rows']),1):
        if r['number']!=n or r['sentenceSha256']!=digest(s) or type(r['matchesCommonRule']) is not bool or not r.get('reason') or not r.get('sourceIds'):
            raise ValueError('Invalid sentence classification')
        if r['matchesCommonRule']:chosen.append(str(n))
    key=''.join(chosen)
    if len(chosen)<2 or key!=card['answer'] or key!=card['answer_verify']:
        raise ValueError('Task-21 manual selection differs from keys: '+card['number'])
    needed={s for r in review['rows'] for s in r['sourceIds']}
    if {e['sourceId'] for e in review['paragraphEvidence']}!=needed or len(review['paragraphEvidence'])!=len(needed):
        raise ValueError('Incomplete task-21 rule evidence')
    for e in review['paragraphEvidence']:
        p=paragraphs.get(e['sourceId'])
        if not p or p['part']!='punctuation' or p['textSha256']!=e['textSha256'] or e['method']!='paragraph_text_read':
            raise ValueError('Stale task-21 evidence')
    pending=[i for i in json.loads(ISSUES.read_text())['issues'] if i['status']=='open' and i.get('affectsExplanation') and card['number'] in i['cardIds']]
    if bool(pending)!=bool(review.get('sourceReviewPending')):
        raise ValueError('Task-21 pending log and explanation disagree')
    if pending and (review['status']!='assistant_rewritten_requires_source_review' or not review.get('sourceReviewNote')):
        raise ValueError('Missing pending task-21 note')
    if not pending and review['status']!='assistant_rewritten_source_linked':
        raise ValueError('Unexpected task-21 status')
    return ss


def render(card, review, paragraphs):
    ss=validate(card,review,paragraphs)
    blocks=[f'Ответ: <b>{card["answer"]}</b>.', 'Общее основание: '+clean(review['commonRule'])]
    if review.get('sourceReviewPending'):blocks.insert(0,'<b>Требует уточнения.</b><br>'+clean(review['sourceReviewNote']))
    for r in review['rows']:
        blocks.append(f'<b>Предложение {r["number"]} — '+('подходит.' if r['matchesCommonRule'] else 'не подходит.')+'</b><br>'+clean(r['reason']))
    blocks.append('Сравните выбранные предложения:<br>'+'<br>'.join('<strong>'+clean(f'({r["number"]}) '+ss[r['number']-1])+'</strong>' for r in review['rows'] if r['matchesCommonRule']))
    return '<br><br>'.join(blocks)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--write',action='store_true');p.add_argument('--report',action='store_true');args=p.parse_args()
    registry=read_registry();_,ps=read_handbook(ROOT/'data/knowledge/sources/lopatin-2007.fb2.zip');ps={p['id']:p for p in ps}
    logpath=ROOT/'dev/docs/content-audit/explanation-reviews.json';log=json.loads(logpath.read_text());writes=[];ids=set()
    for r in registry['cards']:
        if r['id'] in ids:raise ValueError('Duplicate task-21 review')
        ids.add(r['id']);path=ROOT/f'data/card_{r["id"]}.json';card=json.loads(path.read_text());result=render(card,r,ps)
        if result==card.get('explanation',''):continue
        before=digest(card.get('explanation',''))
        if not args.write or before!=r['previousExplanationSha256']:raise ValueError('Stale task-21 explanation')
        card['explanation']=result;writes.append((path,json.dumps(card,ensure_ascii=False,indent=2)+'\n'))
        log['reviews'].append({'changeId':'PUNCTUATION21-'+r['id'],'id':r['id'],'reviewDate':r['reviewDate'],'reviewer':'assistant','status':r['status'],'reason':'Заново классифицированы все исходные предложения по функции указанного знака; разобраны также исключённые номера. Старые объяснения не использовались. Вопросы сохранены в explanations-20-26-issues.json.','answerUnchanged':True,'previousExplanationSha256':before,'explanationSha256':digest(result)})
    if writes:
        writes.append((logpath,json.dumps(log,ensure_ascii=False,indent=2)+'\n'));originals={p:p.read_bytes() for p,_ in writes}
        try:
            for p,t in writes:p.write_text(t)
        except OSError:
            for p,t in originals.items():p.write_bytes(t)
            raise
    if args.report:
        allids={json.loads(p.read_text())['number'] for p in (ROOT/'data').glob('card_*.json') if mapping(json.loads(p.read_text()))['task']==21}
        report={'task':21,'reviewDate':registry['reviewDate'],'taskCards':len(allids),'freshlyReviewedCards':len(ids),'sentencesReviewed':sum(len(r['rows']) for r in registry['cards']),'remainingCards':sorted(allids-ids),'pendingCards':[r['id'] for r in registry['cards'] if r.get('sourceReviewPending')],'independentTeacherAcceptance':False,'cards':sorted(ids)}
        (ROOT/'dev/docs/content-audit/task-21-explanations-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(f'Task 21: {len(ids)} cards checked; {len(writes)-1 if writes else 0} explanations updated')


if __name__=='__main__':main()
