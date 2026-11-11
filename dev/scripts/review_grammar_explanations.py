#!/usr/bin/env python3
"""Reproduce fresh sentence-by-sentence reviews of task 8; preserve FIPI inputs."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
LETTERS = 'АБВГД'
PENDING_NOTE = 'Одно соответствие в этом задании требует предметной проверки. Подтверждённые связи объяснены, спорный случай отмечен отдельно.'

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def frozen(card):
    return digest(json.dumps({k:v for k,v in card.items() if k!='explanation'}, ensure_ascii=False, sort_keys=True))

def load_sources():
    catalog = json.loads((ROOT / 'dev/data/knowledge/grammar_sources.json').read_text())
    sources = {}
    for source in catalog['sources']:
        parsed = urlparse(source['url'])
        grammar_url = parsed.netloc == 'gramota.ru' and (parsed.path.startswith('/biblioteka/spravochniki/') or re.fullmatch(r'/spravka/vopros/[0-9]+', parsed.path) or re.fullmatch(r'/meta/[a-z]+(?:_[0-9]+\.h[0-9]+)?', parsed.path) or parsed.path == '/storage/public/normdicts/orfograficheskij_slovar.pdf')
        fipi_url = parsed.netloc == 'doc.fipi.ru' and re.fullmatch(r'/zhurnal-fipi/PI-[0-9]{4}-[0-9]{2}\.pdf', parsed.path)
        journal_pdf_url = source['url'] == 'https://dcl.bas.bg/wp-content/uploads/2022/11/08_Letuchiy_STONTBgRu2022.pdf'
        journal_url = source['url'] == 'https://cyberleninka.ru/article/n/ukazatelnye-mestoimeniya-v-slozhnopodchinennyh-konstruktsiyah-so-znacheniem-peredachi-vospriyatiya-ili-osmysleniya-informatsii'
        if source['id'] in sources or parsed.scheme != 'https' or not (grammar_url or fipi_url or journal_url or journal_pdf_url or source['url'] == 'https://artefact.lib.ru/languages/rus_ebooks_rg_1645-1668.shtml') or parsed.query or parsed.fragment:
            raise ValueError('Invalid or duplicate grammar source')
        if source.get('sectionFragment') and (source['url'] != 'https://artefact.lib.ru/languages/rus_ebooks_rg_1645-1668.shtml' or source['sectionFragment'] != 'p1658'):
            raise ValueError('Unknown grammar section fragment')
        hash_keys = ('fileSha256','textSha256') if source.get('format') == 'pdf' else ('htmlSha256','textSha256')
        if any(not re.fullmatch('[0-9a-f]{64}', source[key]) for key in hash_keys) or not source['anchor'].strip() or source['readMethod'] != 'section_text_read':
            raise ValueError('Incomplete grammar source evidence')
        sources[source['id']] = source
    return sources

def validate_evidence(review, sources):
    if review['rewriteReview'].get('oldExplanationsUsedAsEvidence') is not False:
        raise ValueError('Fresh grammar review required')
    for row in review['rows']:
        evidence = row.get('grammarEvidence', [])
        if not evidence or len({e['sourceId'] for e in evidence}) != len(evidence):
            raise ValueError('Missing or duplicate grammar evidence')
        for entry in evidence:
            source = sources.get(entry['sourceId'])
            if source is None or entry['textSha256'] != source['textSha256'] or entry['method'] != 'section_text_read':
                raise ValueError('Grammar evidence does not match its source')

def public_refs(review, sources):
    validate_evidence(review, sources)
    return [{'part':row['number'], 'sourceId':e['sourceId'], 'label':sources[e['sourceId']]['citationLabel'], 'url':sources[e['sourceId']]['url'] + ('#page='+str(sources[e['sourceId']]['pdfPage']) if sources[e['sourceId']].get('format') == 'pdf' else '')}
            for row in review['rows'] for e in row['grammarEvidence']]

def render(card, review):
    if review['id'] != card['number'] or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Source task changed')
    if len(card.get('errors', [])) != 5 or len(card.get('sentences', [])) != 9 or len(review['rows']) != 9:
        raise ValueError('Expected five errors and nine sentences')
    pending = [row for row in review['rows'] if row.get('errorIndex') is None]
    if bool(pending) != review.get('sourceReviewPending', False) or len(pending) > 1:
        raise ValueError('Unresolved classification needs an explicit review status')
    if pending and review['status'] != 'assistant_rewritten_requires_source_review':
        raise ValueError('Unresolved grammar cannot be presented as accepted')
    matches, blocks = {}, []
    for number, (sentence, row) in enumerate(zip(card['sentences'], review['rows']), 1):
        if row['number'] != number or digest(sentence) != row['sentenceSha256'] or not row['contextCue'].strip() or row['contextCue'] not in sentence:
            raise ValueError('Reviewed sentence changed')
        unresolved = row['errorIndex'] is None
        index = row.get('historicalErrorIndex') if unresolved else row['errorIndex']
        if unresolved and (row.get('assignmentEvidence') != 'historical_key_only' or not row.get('requiredEvidence', '').strip() or not row.get('suggestedRewrite', '').strip()):
            raise ValueError('Unresolved row needs its provenance, evidence gap, and neutral rewrite')
        if type(index) is not int or not 0 <= index <= 5 or not row['reason'].strip():
            raise ValueError('Invalid grammar classification')
        if index:
            if index in matches or (not unresolved and (not row.get('correction', '').strip() or row['correction'] == sentence)):
                raise ValueError('Duplicate error or missing correction')
            matches[index] = str(number)
            label = ('спорное соответствие '+LETTERS[index-1] if unresolved else LETTERS[index-1]+' — '+re.sub(r'\s+', ' ', card['errors'][index-1]).strip())
        else:
            if row.get('correction'):
                raise ValueError('Control sentence must not have a correction')
            label = 'грамматической ошибки из списка нет'
        block = '<b>Предложение '+str(number)+' — '+html.escape(label)+'.</b> '+html.escape(row['reason'])
        if unresolved:
            block += ' <b>Нейтральная редакция:</b> '+html.escape(row['suggestedRewrite'])
        elif index:
            block += ' <b>Возможное исправление:</b> '+html.escape(row['correction'])
        blocks.append(block)
    if set(matches) != set(range(1,6)):
        raise ValueError('Each error must occur exactly once')
    answer = ''.join(matches[i] for i in range(1,6))
    if answer != card['answer'] or answer != card['answer_verify']:
        raise ValueError('Independent grammar matching differs from the historical key')
    lead = ('По эталону задания: ' if pending else 'Соответствие: ')+', '.join(LETTERS[i-1]+'–'+matches[i] for i in range(1,6))+'.'
    introduction = 'Проверяем все девять предложений. Спорное соответствие отмечено отдельно.' if pending else 'Проверяем все девять предложений: пять содержат указанные ошибки, четыре служат для проверки выбора.'
    return lead+'<br><br>'+introduction+'<br><br>'+'<br><br>'.join(blocks)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    registry = json.loads((ROOT / 'dev/data/knowledge/grammar_card_reviews.json').read_text())
    sources = load_sources()
    log_path = ROOT / 'dev/docs/content-audit/explanation-reviews.json'
    log = json.loads(log_path.read_text())
    prepared = []
    for review in registry['cards']:
        validate_evidence(review, sources)
        path = ROOT / 'data' / ('card_'+review['id']+'.json')
        card = json.loads(path.read_text())
        explanation = render(card, review)
        if explanation == card['explanation']:
            continue
        if not args.write:
            raise ValueError('Explanation differs from fresh grammar review: '+review['id'])
        previous = digest(card['explanation'])
        card['explanation'] = explanation
        prepared.append((path, json.dumps(card, ensure_ascii=False, indent=2)+'\n'))
        log['reviews'].append({'changeId':'GRAMMAR-'+review['id'], 'id':review['id'], 'reviewer':'assistant', 'reviewDate':review['rewriteReview']['date'], 'status':review['status'], 'reason':review['reviewReason'], 'answerUnchanged':True, 'previousExplanationSha256':previous, 'explanationSha256':digest(explanation)})
    if args.write and prepared:
        writes = prepared + [(log_path, json.dumps(log, ensure_ascii=False, indent=2)+'\n')]
        snapshots = {path:path.read_bytes() for path,_ in writes}
        try:
            for path,value in writes:
                path.write_text(value)
        except OSError:
            for path,value in snapshots.items():
                path.write_bytes(value)
            raise
    print(f'Grammar cards checked: {len(registry["cards"])}; updated: {len(prepared)}')

if __name__ == '__main__':
    main()
