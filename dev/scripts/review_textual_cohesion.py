#!/usr/bin/env python3
"""Prepare task-26 links to immediately preceding sentences with explicit linguistic evidence."""
import argparse
import json
import re
from review_punctuation_explanations import ROOT, frozen, digest, clean
from review_isolation_explanations import plain_question
from exam_2027 import mapping
from review_reading_content import sentences

REGISTRY = ROOT / 'dev/data/knowledge/textual_cohesion_card_reviews.json'
ISSUES = ROOT / 'dev/docs/content-audit/explanations-20-26-issues.json'


def read_registry():
    return json.loads(REGISTRY.read_text())


SOURCES = ROOT / 'dev/data/knowledge/textual_cohesion_sources.json'


def load_sources():
    sources = {}
    for src in json.loads(SOURCES.read_text())['sources']:
        text = (ROOT / src['file']).read_text()
        if src['id'] in sources or digest(text) != src['snapshotSha256'] or digest(text.rstrip('\n')) != src['textSha256']:
            raise ValueError('Duplicate or stale lexical snapshot')
        sources[src['id']] = src
    return sources


def target_numbers(card):
    match = re.search(r'Среди предложений\s+(\d+)\s*[–—‒−-]\s*(\d+)', plain_question(card['question']))
    if not match or int(match[1]) < 1 or int(match[1]) > int(match[2]):
        raise ValueError('Unsupported task-26 range')
    return set(range(int(match[1]), int(match[2]) + 1))


def requested_kinds(card):
    question = plain_question(card['question']).casefold()
    match = re.search(r'(?:при помощи|с помощью)(.*?)(?:напишите|запишите)', question)
    if not match:
        raise ValueError('Missing task-26 cohesion request')
    request = match[1]
    patterns = {
        'personal':r'\bличн', 'possessive':r'притяжательн',
        'demonstrative':r'указательн', 'lexical_repeat':r'лексическ.*повтор',
        'word_form':r'\bформ(?:[а-яё]*|\([а-яё]*\))\s+слов',
        'cognate':r'однокоренн', 'conjunction':r'союз', 'adverb':r'нареч',
        'particle':r'частиц', 'synonym':r'синоним', 'determinative':r'определительн',
        'collective_numeral':r'собирательн.*числительн', 'introductory':r'вводн',
    }
    kinds = {kind for kind, pattern in patterns.items() if re.search(pattern, request)}
    if not kinds:
        raise ValueError('Unknown task-26 cohesion request')
    return kinds


def validate(card, review, sources):
    if card['number'] != review['id'] or mapping(card)['task'] != 26 or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Task-26 source changed')
    prov = review['rewriteReview']
    if review['task'] != 26 or not review.get('hint') or not review.get('reason') or prov.get('scope') != 'requested_range_and_each_immediately_previous_sentence' or prov.get('oldExplanationsUsedAsEvidence') is not False or prov.get('independentTeacherAcceptance') is not False:
        raise ValueError('Invalid task-26 provenance')
    expected = target_numbers(card)
    numbers = review['answerNumbers']
    if not numbers or any(type(n) is not int for n in numbers) or sorted(set(numbers)) != numbers or not set(numbers) <= expected or ''.join(map(str,numbers)) != card['answer'] or card['answer'] != card['answer_verify']:
        raise ValueError('Preserved sentence key differs')
    if review['sourceEvidence'].get('method') != 'requested_range_and_previous_context_read' or review['sourceEvidence'].get('textSha256') != digest(plain_question(card['text'])):
        raise ValueError('Stale task-26 passage evidence')
    ss = sentences(card)
    required = expected | ({min(expected)-1} if min(expected) > 1 else set())
    if len(review['evidence']) != len(required) or any(type(e['sentence']) is not int for e in review['evidence']) or {e['sentence'] for e in review['evidence']} != required:
        raise ValueError('Missing task-26 sentence or preceding context')
    for e in review['evidence']:
        n = e['sentence']
        if not 1 <= n <= len(ss) or e['quote'] != ss[n-1] or e['sentenceSha256'] != digest(ss[n-1]):
            raise ValueError('Invalid task-26 quotation')
    allowed = {'personal','possessive','demonstrative','lexical_repeat','word_form','cognate','conjunction','adverb','particle','synonym','determinative','collective_numeral','introductory'}
    if not review['requestedKinds'] or not set(review['requestedKinds']) <= allowed or set(review['requestedKinds']) != requested_kinds(card) or len(review['requestedKinds']) != len(set(review['requestedKinds'])):
        raise ValueError('Unknown cohesion criteria')
    for n in numbers:
        links = [link for link in review['links'] if link['sentence'] == n]
        if {link['kind'] for link in links} != set(review['requestedKinds']):
            raise ValueError('Selected sentence misses a required cohesion means')
    for link in review['links']:
        n = link['sentence']
        if n < 2 or n not in numbers or link['previousSentence'] != n-1 or not link.get('reason'):
            raise ValueError('Cohesion evidence must connect adjacent sentences')
        for value, text in [(link['token'],ss[n-1]), (link['antecedent'],ss[n-2])]:
            if not value or not re.search(r'(?<!\w)' + re.escape(value.casefold()) + r'(?!\w)', text.casefold()):
                raise ValueError(f'Cohesion marker absent: {review["id"]}, link {n-1} -> {n}, marker {value!r}')
    if not review['theoryEvidence']:
        raise ValueError('Missing cohesion theory evidence')
    for e in review['theoryEvidence']:
        src = sources.get(e['sourceId'])
        if not src or src['textSha256'] != e['textSha256'] or src['readMethod'] != e['method']:
            raise ValueError('Stale cohesion theory evidence')
    pending = [i for i in json.loads(ISSUES.read_text())['issues'] if i['status'] == 'open' and i.get('affectsExplanation') and review['id'] in i['cardIds']]
    if bool(pending) != bool(review.get('sourceReviewPending')) or (pending and not review.get('sourceReviewNote')):
        raise ValueError('Pending log and task-26 explanation disagree')
    if review['status'] != ('assistant_rewritten_requires_source_review' if pending else 'assistant_rewritten_source_linked'):
        raise ValueError('Invalid task-26 review status')


def render(card, review, sources):
    validate(card, review, sources)
    labels = {'personal':'Личное местоимение','possessive':'Притяжательное местоимение','demonstrative':'Указательное местоимение','lexical_repeat':'Лексический повтор','word_form':'Формы одного слова','cognate':'Однокоренные слова','conjunction':'Союз','adverb':'Наречие','particle':'Частица','synonym':'Контекстные синонимы','determinative':'Определительное местоимение','collective_numeral':'Собирательное числительное','introductory':'Вводное слово'}
    reason = clean(review['reason'])
    if opening := review.get('italicOpening'):
        opening = clean(opening)
        if not reason.startswith(opening + ' '):
            raise ValueError('Italic opening does not match the explanation')
        reason = f'<i>{opening}</i>' + reason[len(opening):]
    blocks = ['Ответ: <b>' + clean(card['answer']) + '</b>.', reason]
    if review.get('sourceReviewPending'):
        blocks.insert(0, '<b>Требует уточнения.</b><br>' + clean(review['sourceReviewNote']))
    for n in review['answerNumbers']:
        links = [link for link in review['links'] if link['sentence'] == n]
        blocks.append('<b>Связь ' + str(n-1) + ' → ' + str(n) + '.</b><br>' + '<br>'.join(clean(labels[link['kind']]) + ': «' + clean(link['antecedent']) + '» → «' + clean(link['token']) + '». ' + clean(link['reason']) for link in links))
    footnote = review.get('footnote')
    marker = '<sup>1</sup>' if footnote else ''
    if other_candidates := review.get('otherCandidates'):
        blocks.append('<b>Другие предложения диапазона.</b>' + marker + '<br>' + clean(other_candidates))
    elif footnote:
        blocks[-1] += marker
    blocks.append('Основание — исходный текст:<br>' + '<br>'.join(f'({e["sentence"]}) «{clean(e["quote"])}»' for e in review['evidence']))
    blocks.append('Источники критериев: ' + '; '.join(clean(sources[e['sourceId']]['citationLabel']) for e in review['theoryEvidence']) + '.<br>Конкретные связи установлены по тексту; справочник не является ключом ФИПИ.')
    note = f'<p class="editorial-note">{marker} {clean(footnote)}</p>' if footnote else ''
    return '<br><br>'.join(blocks) + note


def public_refs(review, sources):
    return [{'part':1, 'sourceId':e['sourceId'], 'label':sources[e['sourceId']]['citationLabel'], 'url':sources[e['sourceId']]['url']} for e in review['theoryEvidence']]


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
            raise ValueError('Duplicate task-26 review')
        ids.add(r['id'])
        path = ROOT / f'data/card_{r["id"]}.json'
        card = json.loads(path.read_text())
        result = render(card, r, sources)
        if result == card.get('explanation', ''):
            continue
        before = digest(card.get('explanation', ''))
        if not args.write or before != r['previousExplanationSha256']:
            raise ValueError('Stale task-26 explanation')
        card['explanation'] = result
        writes.append((path, json.dumps(card, ensure_ascii=False, indent=2) + '\n'))
        log['reviews'].append({'changeId':'COHESION26-' + r['id'], 'id':r['id'], 'reviewDate':r['reviewDate'], 'reviewer':'assistant', 'status':r['status'], 'reason':'Заново прочитан заданный диапазон с предыдущим контекстом. Для выбранных предложений названы все требуемые средства связи с непосредственно предыдущим предложением; приведены точные цитаты и индивидуальная подсказка. Старые объяснения не использовались.', 'answerUnchanged':True, 'previousExplanationSha256':before, 'explanationSha256':digest(result)})
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
        allids = {c['number'] for p in (ROOT / 'data').glob('card_*.json') if mapping(c := json.loads(p.read_text()))['task'] == 26}
        report = {'task':26, 'reviewDate':registry['reviewDate'], 'taskCards':len(allids), 'freshlyReviewedCards':len(ids), 'requestedSentencesReviewed':sum(len(target_numbers(json.loads((ROOT / f'data/card_{r["id"]}.json').read_text()))) for r in registry['cards']), 'remainingCards':sorted(allids-ids), 'pendingCards':[r['id'] for r in registry['cards'] if r.get('sourceReviewPending')], 'independentTeacherAcceptance':False, 'cards':sorted(ids)}
        (ROOT / 'dev/docs/content-audit/task-26-explanations-coverage.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Task 26: {len(ids)} cards checked; {len(writes)-1 if writes else 0} explanations updated')


if __name__ == '__main__':
    main()
