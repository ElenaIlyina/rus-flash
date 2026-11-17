#!/usr/bin/env python3
"""Validate fresh task-25 lexical answers, requested fragments and dictionary evidence."""
import argparse
import json
import re
from review_punctuation_explanations import ROOT, frozen, digest, clean
from review_isolation_explanations import plain_question
from exam_2027 import mapping
from review_reading_content import sentences

REGISTRY = ROOT / 'dev/data/knowledge/lexical_analysis_card_reviews.json'
ISSUES = ROOT / 'dev/docs/content-audit/explanations-20-26-issues.json'


def read_registry():
    return json.loads(REGISTRY.read_text())


SOURCES = ROOT / 'dev/data/knowledge/lexical_analysis_sources.json'


def load_sources():
    sources = {}
    for src in json.loads(SOURCES.read_text())['sources']:
        text = (ROOT / src['file']).read_text()
        if src['id'] in sources or digest(text) != src['snapshotSha256'] or digest(text.rstrip('\n')) != src['textSha256']:
            raise ValueError('Duplicate or stale lexical snapshot')
        sources[src['id']] = src
    return sources


def target_numbers(card):
    match = re.search(r'Из предложени[йя]\s+([0-9\s,–—‒−-]+)\s+выпишите', plain_question(card['question']), re.IGNORECASE)
    if not match:
        raise ValueError('Unsupported task-25 sentence scope')
    scope = match[1].strip()
    numbers = set()
    for part in scope.split(','):
        bounds = re.fullmatch(r'\s*(\d+)(?:\s*[–—‒−-]\s*(\d+))?\s*', part)
        if not bounds:
            raise ValueError('Invalid task-25 sentence scope')
        first, last = int(bounds[1]), int(bounds[2] or bounds[1])
        if first > last:
            raise ValueError('Reversed task-25 range')
        numbers.update(range(first, last + 1))
    return numbers


def validate(card, review, sources):
    if card['number'] != review['id'] or mapping(card)['task'] != 25 or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Task-25 source changed')
    prov = review['rewriteReview']
    if review['task'] != 25 or not review.get('hint') or prov.get('scope') != 'all_requested_sentences_and_lexical_meaning' or prov.get('oldExplanationsUsedAsEvidence') is not False or prov.get('independentTeacherAcceptance') is not False:
        raise ValueError('Invalid task-25 provenance')
    if review['answer'] != card['answer'] or review['answer'] != card['answer_verify'] or not review.get('reason') or not review.get('contrast'):
        raise ValueError('Lexical answer differs from preserved key or missing reasoning')
    if review['sourceEvidence'].get('method') != 'requested_fragments_and_context_read' or review['sourceEvidence'].get('textSha256') != digest(plain_question(card['text'])):
        raise ValueError('Stale task-25 passage evidence')
    ss = sentences(card)
    expected = target_numbers(card)
    if not expected <= {e['sentence'] for e in review['evidence']}:
        raise ValueError('Requested passage range not fully checked')
    seen = set()
    for e in review['evidence']:
        n = e['sentence']
        if type(n) is not int or n in seen or not 1 <= n <= len(ss) or e['quote'] != ss[n-1] or e['sentenceSha256'] != digest(ss[n-1]):
            raise ValueError('Invalid task-25 quotation')
        seen.add(n)
    target = ' '.join(ss[n-1] for n in sorted(expected)).casefold()
    for token in review['answer'].split():
        if not re.search(r'(?<!\w)' + re.escape(token.casefold()) + r'(?!\w)', target):
            raise ValueError('Answer form absent from requested passage')
    if not review['lexicalEvidence']:
        raise ValueError('Missing lexical source evidence')
    for e in review['lexicalEvidence']:
        src = sources.get(e['sourceId'])
        if not src or src['textSha256'] != e['textSha256'] or src['readMethod'] != e['method']:
            raise ValueError('Stale lexical source evidence')
    pending = [i for i in json.loads(ISSUES.read_text())['issues'] if i['status'] == 'open' and i.get('affectsExplanation') and review['id'] in i['cardIds']]
    if bool(pending) != bool(review.get('sourceReviewPending')) or (pending and not review.get('sourceReviewNote')):
        raise ValueError('Pending log and lexical explanation disagree')
    if review['status'] != ('assistant_rewritten_requires_source_review' if pending else 'assistant_rewritten_source_linked'):
        raise ValueError('Invalid task-25 review status')


def render(card, review, sources):
    validate(card, review, sources)
    blocks = ['Ответ: <b>' + clean(review['answer']) + '</b>.', clean(review['reason']), clean(review['contrast'])]
    if review.get('sourceReviewPending'):
        blocks.insert(0, '<b>Требует уточнения.</b><br>' + clean(review['sourceReviewNote']))
    blocks.append('Основание — исходный текст:<br>' + '<br>'.join(f'({e["sentence"]}) «{clean(e["quote"])}»' for e in review['evidence']))
    blocks.append('Источники лексической проверки: ' + '; '.join(clean(sources[e['sourceId']]['citationLabel']) for e in review['lexicalEvidence']) + '.<br>Словарные значения и общие определения соотнесены с контекстом; они не являются ключом ФИПИ.')
    return '<br><br>'.join(blocks)


def public_refs(review, sources):
    return [{'part':1, 'sourceId':e['sourceId'], 'label':sources[e['sourceId']]['citationLabel'], 'url':sources[e['sourceId']]['url']} for e in review['lexicalEvidence']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    registry = read_registry()
    sources = load_sources()
    logpath = ROOT / 'dev/docs/content-audit/explanation-reviews.json'
    log = json.loads(logpath.read_text())
    writes, ids = [], set()
    for r in registry['cards']:
        if r['id'] in ids:
            raise ValueError('Duplicate task-25 review')
        ids.add(r['id'])
        path = ROOT / f'data/card_{r["id"]}.json'
        card = json.loads(path.read_text())
        result = render(card, r, sources)
        if result == card.get('explanation', ''):
            continue
        before = digest(card.get('explanation', ''))
        if not args.write or before != r['previousExplanationSha256']:
            raise ValueError('Stale task-25 explanation')
        card['explanation'] = result
        writes.append((path, json.dumps(card, ensure_ascii=False, indent=2) + '\n'))
        log['reviews'].append({'changeId':'LEXICAL25-' + r['id'], 'id':r['id'], 'reviewDate':r['reviewDate'], 'reviewer':'assistant', 'status':r['status'], 'reason':'Заново прочитаны все предложения заданного диапазона, лексическое значение проверено по источникам и контексту. Сохранены формы слов исходного текста, приведены цитаты и индивидуальная подсказка. Старые объяснения не использовались.', 'answerUnchanged':True, 'previousExplanationSha256':before, 'explanationSha256':digest(result)})
    if writes:
        writes.append((logpath, json.dumps(log, ensure_ascii=False, indent=2) + '\n'))
        originals = {p:p.read_bytes() for p, _ in writes}
        try:
            for p, t in writes:
                p.write_text(t)
        except OSError:
            for p, t in originals.items():
                p.write_bytes(t)
            raise
    if args.report:
        allids = {c['number'] for p in (ROOT / 'data').glob('card_*.json') if mapping(c := json.loads(p.read_text()))['task'] == 25}
        report = {'task':25, 'reviewDate':registry['reviewDate'], 'taskCards':len(allids), 'freshlyReviewedCards':len(ids), 'requestedSentencesReviewed':sum(len(target_numbers(json.loads((ROOT / f'data/card_{r["id"]}.json').read_text()))) for r in registry['cards']), 'remainingCards':sorted(allids-ids), 'pendingCards':[r['id'] for r in registry['cards'] if r.get('sourceReviewPending')], 'independentTeacherAcceptance':False, 'cards':sorted(ids)}
        (ROOT / 'dev/docs/content-audit/task-25-explanations-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Task 25: {len(ids)} cards checked; {len(writes)-1 if writes else 0} explanations updated')


if __name__ == '__main__':
    main()
