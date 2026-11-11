#!/usr/bin/env python3
"""Reproduce context-reviewed solid, separate, and hyphenated spellings."""
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

LETTERS = 'А-ЯЁа-яё'
MARKED = re.compile(r'(?:\(['+LETTERS+r']+\)\s*)+['+LETTERS+r']+(?:\(['+LETTERS+r']+\))*|['+LETTERS+r']+(?:\(['+LETTERS+r']+\))+')
SEPARATORS = {'solid':'', 'separate':' ', 'hyphen':'-'}
LABELS = {'solid':'слитно', 'separate':'раздельно', 'hyphen':'через дефис'}

def plain(value):
    return html.unescape(re.sub('<[^>]*>', '', value))

def parts(value):
    return re.findall('['+LETTERS+']+', value.lower())

def frozen(card):
    return hashlib.sha256(json.dumps({k:v for k,v in card.items() if k!='explanation'},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def render(card, review):
    if frozen(card) != review['sourceContentSha256']:
        raise ValueError('Source task changed: '+card['number'])
    question = plain(card['question']).lower()
    target = 'hyphen' if 'через дефис' in question else 'separate' if 'раздельно' in question else 'solid' if 'слитно' in question else None
    word_answer = 'выпишите эти два слова' in question
    if target is None or (not word_answer and 'запишите номера ответов' not in question):
        raise ValueError('Unsupported instruction')
    if len(card['variants']) != len(review['rows']):
        raise ValueError('Option count differs')
    selected, answers, blocks = [], [], []
    for number, (variant, row) in enumerate(zip(card['variants'], review['rows']), 1):
        source_units = list(MARKED.finditer(plain(variant)))
        if number != row['number'] or len(source_units) != len(row['items']) or len(source_units) != 2:
            raise ValueError('Marked units differ from the reviewed source')
        if hashlib.sha256(variant.encode()).hexdigest() != row['variantSha256']:
            raise ValueError('Reviewed context changed')
        possible, definite, units, completed_words = [], [], [], []
        for part_number, (match, item) in enumerate(zip(source_units, row['items']), 1):
            source_parts = parts(match[0])
            if source_parts != item['sourceParts']:
                raise ValueError('Reviewed parts differ from source')
            edited_parts = list(source_parts)
            for correction in item.get('sourceCorrections', []):
                if (card['number'], number, part_number, source_parts,
                    correction.get('from'), correction.get('to')) != ('63227E', 4, 2,
                        ['по','осенему'], 'осенему', 'осеннему'):
                    raise ValueError('Unsupported editorial source normalization')
                edited_parts[1] = correction['to']
            spelling = item['spelling']
            options = item.get('spellingOptions', [spelling])
            if spelling not in SEPARATORS or not options or spelling not in options or any(s not in SEPARATORS for s in options):
                raise ValueError('Invalid spelling options')
            completed = SEPARATORS[spelling].join(edited_parts)
            if completed != item['completed'] or not item['reason'].strip():
                raise ValueError('Completed form differs from source parts')
            possible.append(target in options)
            definite.append(set(options) == {target})
            completed_words.append(completed)
            display_forms = ' / '.join(SEPARATORS[s].join(edited_parts) for s in options)
            labels = ' / '.join(LABELS[s] for s in options)
            units.append('<b>'+html.escape(display_forms)+'</b> — '+labels+'. '+html.escape(item['reason']))
        can_match, must_match = all(possible), all(definite)
        if can_match != must_match:
            raise ValueError('Unresolved semantic spelling changes the selected answer')
        if must_match:
            selected.append(str(number))
        answers.append(completed_words)
        blocks.append(f'<b>Вариант {number} — '+('подходит' if must_match else 'не подходит')+'.</b> '+' '.join(units))
    if word_answer:
        if len(selected) != 1:
            raise ValueError('Expected exactly one word-pair answer')
        answer = ' '.join(answers[int(selected[0])-1])
        canonical = lambda value: re.sub(r'\s+', ' ', value).strip().casefold().replace('ё','е')
        if canonical(answer) != canonical(card['answer']) or canonical(answer) != canonical(card['answer_verify']):
            raise ValueError('Reviewed word pair differs from the historical key: '+card['number'])
        lead = 'Ответ: '+html.escape(answer)+'.'
    else:
        answer = ''.join(selected)
        bits = ''.join('1' if str(i+1) in selected else '0' for i in range(len(review['rows'])))
        if answer != card['answer'] or bits != card['answer_verify']:
            raise ValueError('Reviewed selection differs from the historical key: '+card['number'])
        lead = 'Верно: '+', '.join(selected)+'.'
    return (lead+'<br><br>Все выделенные единицы выбранного варианта должны писаться '+LABELS[target]+
            '. Проверяем каждую по её значению в предложении.<br><br>'+'<br><br>'.join(blocks))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    registry = json.loads((ROOT / 'dev/data/knowledge/joined_card_reviews.json').read_text())
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
            raise ValueError('Explanation differs from reviewed contexts: '+review['id'])
        previous = hashlib.sha256(card['explanation'].encode()).hexdigest()
        card['explanation'] = explanation
        prepared.append((path, json.dumps(card, ensure_ascii=False, indent=2)+'\n'))
        log['reviews'].append({'changeId':'JOINED-'+review['id'], 'id':review['id'],
            'reviewer':'assistant', 'reviewDate':review['rewriteReview']['date'], 'status':review['status'],
            'reason':review['reviewReason'], 'answerUnchanged':True, 'previousExplanationSha256':previous,
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
    print(f'Joined spellings checked: {len(registry["cards"])}; updated: {len(prepared)}')

if __name__ == '__main__':
    main()
