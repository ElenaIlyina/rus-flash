#!/usr/bin/env python3
"""Reproduce reviewed Н/НН explanations; never rewrite FIPI questions or keys."""
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

MARKED = re.compile(r'([А-ЯЁа-яёA-Za-z\u0301-]+)\((\d+)\)([А-ЯЁа-яёA-Za-z\u0301-]+)')

def plain(value):
    return html.unescape(re.sub('<[^>]*>', '', value))

def frozen(card):
    return hashlib.sha256(json.dumps({k:v for k,v in card.items() if k!='explanation'},
                                    sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def render(card, review):
    if frozen(card) != review['sourceContentSha256']:
        raise ValueError('Source task changed: ' + card['number'])
    text = plain(card['question'])
    instruction = text.split('\n', 1)[0]
    target = 1 if re.search(r'одна\s+буква\s+Н', instruction, re.I) else 2 if 'НН' in instruction else None
    if target is None or card['variants']:
        raise ValueError('Unsupported numbered Н/НН instruction')
    positions = list(MARKED.finditer(text))
    if len(positions) != len(review['rows']):
        raise ValueError('Position count differs')
    selected, blocks = [], []
    for index, (match, row) in enumerate(zip(positions, review['rows']), 1):
        if int(match[2]) != index or row['number'] != index:
            raise ValueError('Position numbers differ')
        count = row['nCount']
        if type(count) is not int or count not in (1, 2):
            raise ValueError('Expected one or two Н')
        prefix, suffix = match[1], match[3]
        for glyph in row.get('sourceGlyphs', []):
            if (card['number'], index, glyph.get('from'), glyph.get('to')) != ('C6AFC3', 1, 'e', 'е') or prefix.count('e') != 1:
                raise ValueError('Unsupported source glyph normalization')
            prefix = prefix.replace('e', 'е')
        completed = prefix + 'н' * count + suffix
        if completed != row['word']:
            raise ValueError('Word differs from numbered source position')
        if row.get('contextCue'):
            normalize = lambda value: re.sub(r'\s+', ' ', value).casefold().replace('ё', 'е')
            if normalize(row['contextCue']) not in normalize(text):
                raise ValueError('Context cue absent from source passage')
        if not row['reason'].strip():
            raise ValueError('Missing grammatical reason')
        fits = count == target
        if fits:
            selected.append(str(index))
        blocks.append(f'<b>{index}. '+html.escape(completed)+'</b> — '+('НН' if count == 2 else 'Н')+
                      ('; подходит.' if fits else '; не подходит.')+' '+html.escape(row['reason']))
    answer = ''.join(selected)
    if answer != card['answer'] or answer != card['answer_verify']:
        raise ValueError('Reviewed selection differs from the historical key: ' + card['number'])
    return ('Верно: '+', '.join(selected)+'.<br><br>Ищем позиции с '+
            ('одной Н' if target == 1 else 'двумя Н')+
            '. Для каждой формы проверим её образование и роль в предложении.<br><br>'+
            '<br><br>'.join(blocks))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    registry = json.loads((ROOT / 'dev/data/knowledge/n_card_reviews.json').read_text())
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
            raise ValueError('Explanation differs from reviewed positions: ' + review['id'])
        previous = hashlib.sha256(card['explanation'].encode()).hexdigest()
        card['explanation'] = explanation
        prepared.append((path, json.dumps(card, ensure_ascii=False, indent=2)+'\n'))
        log['reviews'].append({'changeId':'N-'+review['id'], 'id':review['id'],
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
    print(f'Н/НН explanations checked: {len(registry["cards"])}; updated: {len(prepared)}')

if __name__ == '__main__':
    main()
