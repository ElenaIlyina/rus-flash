#!/usr/bin/env python3
"""Reproduce reviewed НЕ/НИ explanations without changing source tasks or keys."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from handbook_fb2 import read_handbook
from review_prefix_explanations import validate_rule_evidence

TOKEN = re.compile(r'\((НЕ|НИ)\)\s*([а-яё\u0301]+(?:-[а-яё\u0301]+)*)', re.I)

def plain(value):
    return html.unescape(re.sub('<[^>]*>', '', value))

def frozen(card):
    return hashlib.sha256(json.dumps({k:v for k,v in card.items() if k!='explanation'},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def render(card, review):
    if frozen(card) != review['sourceContentSha256']:
        raise ValueError('Source task changed: ' + card['number'])
    question = plain(card['question']).lower()
    target = 'separate' if 'раздельно' in question else 'solid' if 'слитно' in question else None
    word_answer = 'выпишите это слово' in question
    if not target or (not word_answer and 'запишите номера ответов' not in question):
        raise ValueError('Unsupported instruction')
    if len(review['rows']) != len(card['variants']):
        raise ValueError('Option count differs')
    selected, blocks, spellings = [], [], []
    for number, (source, row) in enumerate(zip(card['variants'], review['rows']), 1):
        matches = list(TOKEN.finditer(plain(source)))
        if len(matches) != 1 or row['number'] != number:
            raise ValueError('Expected one marked particle per source option')
        match = matches[0]
        particle, word = match[1].lower(), match[2].lower()
        if row['particle'] != particle or row['word'] != word:
            raise ValueError('Reviewed word differs from the source option')
        if row['variantSha256'] != hashlib.sha256(source.encode()).hexdigest():
            raise ValueError('Reviewed context changed')
        if row.get('contextCue'):
            normalize = lambda value: re.sub(r'\s+', ' ', plain(value)).casefold().replace('ё', 'е')
            if normalize(row['contextCue']) not in normalize(source):
                raise ValueError('Contextual evidence absent from source option')
        spelling = row['spelling']
        if spelling not in {'solid', 'separate'} or not row['reason'].strip():
            raise ValueError('Incomplete spelling decision')
        completed = particle + ('' if spelling == 'solid' else ' ') + word
        spellings.append(completed)
        fits = spelling == target
        if fits:
            selected.append(str(number))
        blocks.append(f'<b>Вариант {number} — '+('подходит' if fits else 'не подходит')+
                      '.</b> '+html.escape(completed)+': '+('слитно' if spelling == 'solid' else 'раздельно')+
                      '. '+html.escape(row['reason']))
    if word_answer:
        if len(selected) != 1:
            raise ValueError('Word-answer exercise must select exactly one option')
        answer = spellings[int(selected[0])-1]
        canonical = lambda value: value.casefold().replace('ё', 'е').replace('\u0301', '').strip()
        if canonical(answer) != canonical(card['answer']) or canonical(answer) != canonical(card['answer_verify']):
            raise ValueError('Reviewed word differs from the historical key: ' + card['number'])
        lead = 'Ответ: '+html.escape(answer)+'.'
    else:
        answer = ''.join(selected)
        bits = ''.join('1' if str(i+1) in selected else '0' for i in range(len(spellings)))
        if answer != card['answer'] or bits != card['answer_verify']:
            raise ValueError('Reviewed selection differs from the historical key: ' + card['number'])
        lead = 'Верно: '+', '.join(selected)+'.'
    intro = ('В этом задании требуется '+('слитное' if target == 'solid' else 'раздельное')+
             ' написание. Проверяем часть речи, значение и зависимые слова в каждом предложении.')
    return lead+'<br><br>'+intro+'<br><br>'+'<br><br>'.join(blocks)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    registry_path = ROOT / 'dev/data/knowledge/negation_card_reviews.json'
    registry = json.loads(registry_path.read_text())
    _, paragraphs = read_handbook(ROOT / 'data/knowledge/sources/lopatin-2007.fb2.zip')
    paragraphs = {p['id']:p for p in paragraphs}
    log_path = ROOT / 'dev/docs/content-audit/explanation-reviews.json'
    log = json.loads(log_path.read_text())
    prepared = []
    for review in registry['cards']:
        validate_rule_evidence(review, paragraphs)
        path = ROOT / 'data' / f'card_{review["id"]}.json'
        card = json.loads(path.read_text())
        explanation = render(card, review)
        if explanation == card['explanation']:
            continue
        if not args.write:
            raise ValueError('Explanation differs from reviewed options: ' + review['id'])
        previous = hashlib.sha256(card['explanation'].encode()).hexdigest()
        card['explanation'] = explanation
        prepared.append((path, json.dumps(card, ensure_ascii=False, indent=2)+'\n'))
        log['reviews'].append({'changeId':'NEGATION-'+review['id'], 'id':review['id'],
            'reviewer':'assistant', 'reviewDate':review['rewriteReview']['date'],
            'status':review['status'], 'reason':review['reviewReason'], 'answerUnchanged':True,
            'previousExplanationSha256':previous,
            'explanationSha256':hashlib.sha256(explanation.encode()).hexdigest()})
    if args.write and prepared:
        writes = prepared + [(log_path, json.dumps(log, ensure_ascii=False, indent=2)+'\n')]
        snapshots = {path:path.read_bytes() for path,_ in writes}
        try:
            for path, value in writes:
                path.write_text(value)
        except OSError:
            for path, value in snapshots.items():
                path.write_bytes(value)
            raise
    print(f'Negation explanations checked: {len(registry["cards"])}; updated: {len(prepared)}')

if __name__ == '__main__':
    main()
