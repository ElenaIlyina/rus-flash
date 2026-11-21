#!/usr/bin/env python3
"""Validate and publish fresh task-22 matching explanations against source snapshots."""
import argparse
import json
import re
from review_punctuation_explanations import ROOT, frozen, digest, clean
from review_isolation_explanations import plain_question
from exam_2027 import mapping

REGISTRY = ROOT / 'dev/data/knowledge/rhetoric_card_reviews.json'
SOURCES = ROOT / 'dev/data/knowledge/rhetoric_sources.json'
ISSUES = ROOT / 'dev/docs/content-audit/explanations-20-26-issues.json'


def read_registry():
    return json.loads(REGISTRY.read_text())


def load_sources():
    sources = {}
    for s in json.loads(SOURCES.read_text())['sources']:
        if s['id'] in sources or digest((ROOT / s['file']).read_text()) != s['snapshotSha256']:
            raise ValueError('Duplicate or stale rhetoric source: ' + s['id'])
        sources[s['id']] = s
    return sources


def terms(card):
    q = plain_question(card['question']).split('Список терминов:', 1)[-1]
    ms = list(re.finditer(r'(?<!\d)([1-9])\)', q))[-9:]
    if [int(m[1]) for m in ms] != list(range(1, 10)):
        raise ValueError('Invalid term list')
    return [re.split(r'Запишите|Заполните', q[m.end():ms[i+1].start() if i+1 < 9 else len(q)])[0].strip() for i, m in enumerate(ms)]


def fragments(card):
    q = plain_question(card['question'])
    ms = list(re.finditer(r'([АБВГД])\)', q))
    if [m[1] for m in ms] != list('АБВГД'):
        raise ValueError('Invalid modern matching fragments')
    end = re.search(r'(?<!\d)1\)', q[ms[-1].end():]).start() + ms[-1].end()
    return [q[m.end():ms[i+1].start() if i+1 < 5 else end].strip() for i, m in enumerate(ms)]


def validate(card, review, sources):
    if card['number'] != review['id'] or mapping(card)['task'] != 22 or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Task-22 source changed')
    modern = not card.get('text')
    expected_format = 'modern_matching' if modern else 'historical_review'
    prov = review['rewriteReview']
    if review['task'] != 22 or review['format'] != expected_format or not review.get('hint') or prov.get('scope') != 'all_matching_fragments' or prov.get('oldExplanationsUsedAsEvidence') is not False or prov.get('independentTeacherAcceptance') is not False:
        raise ValueError('Invalid task-22 provenance')
    rows = review['rows']
    if len(rows) != (5 if modern else 4):
        raise ValueError('Incomplete matching coverage')
    choices = terms(card)
    fs = fragments(card) if modern else []
    raw = plain_question(card['question'] + ' ' + card.get('text', ''))
    for n, r in enumerate(rows, 1):
        if r['number'] != n or r['letter'] != 'АБВГД'[n-1] or type(r['termNumber']) is not int or not 1 <= r['termNumber'] <= 9 or r['term'] != choices[r['termNumber']-1] or not r.get('reason') or not r.get('quote'):
            raise ValueError('Invalid term assignment: ' + review['id'])
        if (modern and r['quote'] != fs[n-1]) or (not modern and r['quote'] not in raw):
            raise ValueError('Quote absent from source: ' + review['id'] + ' ' + r['letter'] + ' ' + r['quote'])
        if not r['sourceEvidence']:
            raise ValueError('Missing rhetoric evidence')
        for e in r['sourceEvidence']:
            s = sources.get(e['sourceId'])
            if not s or s['textSha256'] != e['textSha256'] or s['readMethod'] != e['method']:
                raise ValueError('Stale rhetoric evidence')
    key = ''.join(str(r['termNumber']) for r in rows)
    if key != card['answer'] or key != card['answer_verify']:
        raise ValueError('Manual matching differs from key')
    pending = [i for i in json.loads(ISSUES.read_text())['issues'] if i['status'] == 'open' and i.get('affectsExplanation') and review['id'] in i['cardIds']]
    if bool(pending) != bool(review.get('sourceReviewPending')) or (pending and not review.get('sourceReviewNote')):
        raise ValueError('Pending log and task-22 explanation disagree')
    if review['status'] != ('assistant_rewritten_requires_source_review' if pending else 'assistant_rewritten_source_linked'):
        raise ValueError('Invalid rhetoric review status')


def render(card, review, sources):
    validate(card, review, sources)
    blocks = [f'Ответ: <b>{card["answer"]}</b>.']
    footnotes = []
    if review.get('sourceReviewPending'):
        blocks.insert(0, '<b>Требует уточнения.</b><br>' + clean(review['sourceReviewNote']))
    if guide := review.get('termGuide'):
        guide_rows = ''.join(
            f'<tr><th>{clean(entry["term"])}</th><td>{clean(entry["meaning"])}</td><td>{clean(entry["example"])}</td></tr>'
            for entry in guide
        )
        blocks.append('<table><thead><tr><th>Термин</th><th>Что означает</th><th>В этой карточке</th></tr></thead>'
                      f'<tbody>{guide_rows}</tbody></table>')
    for r in review['rows']:
        citations = '; '.join(sources[e['sourceId']]['citationLabel'] for e in r['sourceEvidence'])
        marker = ''
        if r.get('footnote'):
            marker = f'<sup>{len(footnotes) + 1}</sup>'
            footnotes.append(f'<p class="editorial-note">{marker} {clean(r["footnote"])}</p>')
        blocks.append(f'<b>{r["letter"]} — {r["termNumber"]}) {clean(r["term"])}.</b><br>«{clean(r["quote"])}»{marker}<br>' + clean(r['reason']) + '<br>Источник: ' + clean(citations) + '.')
    return '<br><br>'.join(blocks) + ''.join(footnotes)


def public_refs(review, sources):
    return [{'part':r['number'], 'sourceId':e['sourceId'], 'label':sources[e['sourceId']]['citationLabel'], 'url':sources[e['sourceId']]['url']} for r in review['rows'] for e in r['sourceEvidence'] if (sources[e['sourceId']].get('url') or '').startswith('https:')]


def local_refs(review, sources):
    refs = []
    for r in review['rows']:
        for e in r['sourceEvidence']:
            s = sources[e['sourceId']]
            if (s.get('url') or '').startswith('#knowledge?source='):
                refs.append({'part':r['number'], 'sourceId':s['url'].split('source=', 1)[1], 'label':s['citationLabel']})
    return refs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write', action='store_true'); p.add_argument('--report', action='store_true'); args = p.parse_args()
    registry = read_registry(); sources = load_sources()
    logpath = ROOT / 'dev/docs/content-audit/explanation-reviews.json'; log = json.loads(logpath.read_text()); writes = []; ids = set()
    for r in registry['cards']:
        if r['id'] in ids: raise ValueError('Duplicate task-22 review')
        ids.add(r['id']); path = ROOT / f'data/card_{r["id"]}.json'; card = json.loads(path.read_text()); result = render(card, r, sources)
        if result == card.get('explanation', ''): continue
        before = digest(card.get('explanation', ''))
        if not args.write or before != r['previousExplanationSha256']: raise ValueError('Stale task-22 explanation')
        card['explanation'] = result; writes.append((path, json.dumps(card, ensure_ascii=False, indent=2) + '\n'))
        log['reviews'].append({'changeId':'RHETORIC22-' + r['id'], 'id':r['id'], 'reviewDate':r['reviewDate'], 'reviewer':'assistant', 'status':r['status'], 'reason':'Заново разобраны все сопоставления по исходным цитатам и определениям в источниках. Старые объяснения не использовались; сомнения сохранены в explanations-20-26-issues.json.', 'answerUnchanged':True, 'previousExplanationSha256':before, 'explanationSha256':digest(result)})
    if writes:
        writes.append((logpath, json.dumps(log, ensure_ascii=False, indent=2) + '\n')); originals = {p:p.read_bytes() for p, _ in writes}
        try:
            for p, t in writes: p.write_text(t)
        except OSError:
            for p, t in originals.items(): p.write_bytes(t)
            raise
    if args.report:
        allids = {c['number'] for p in (ROOT / 'data').glob('card_*.json') if mapping(c := json.loads(p.read_text()))['task'] == 22}
        report = {'task':22, 'reviewDate':registry['reviewDate'], 'taskCards':len(allids), 'freshlyReviewedCards':len(ids), 'fragmentsReviewed':sum(len(r['rows']) for r in registry['cards']), 'remainingCards':sorted(allids-ids), 'pendingCards':[r['id'] for r in registry['cards'] if r.get('sourceReviewPending')], 'independentTeacherAcceptance':False, 'cards':sorted(ids)}
        (ROOT / 'dev/docs/content-audit/task-22-explanations-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Task 22: {len(ids)} cards checked; {len(writes)-1 if writes else 0} explanations updated')


if __name__ == '__main__':
    main()
