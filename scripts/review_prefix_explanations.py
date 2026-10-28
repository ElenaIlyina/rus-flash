#!/usr/bin/env python3
"""Reproduce source-linked row explanations for reviewed spelling exercises.

Default: check only. --write updates explanations and appends immutable review records.
Does not change answers, source questions, or variants. Word forms are editorial data,
not guessed by the script. Mechanical validation is not full teacher acceptance.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def variants(card):
    values=card['variants']
    if len(values)==1:
        values=re.split(r'(?=\d\))',values[0])
    return [re.sub(r'^\s*\d\)\s*','',v).strip() for v in values if v.strip()]


def render(card,review):
    frozen={k:v for k,v in card.items() if k!='explanation'}
    if review.get('sourceContentSha256') and hashlib.sha256(json.dumps(frozen,sort_keys=True,ensure_ascii=False).encode()).hexdigest()!=review['sourceContentSha256']:
        raise ValueError('Source content changed; author approval and re-review required: '+card['number'])
    rows=variants(card)
    if len(rows)!=len(review['rows']):raise ValueError('Row count mismatch: '+card['number'])
    kind=review.get('kind','same_letter_gap')
    if kind not in {'same_letter_gap','checked_root_vowels'}:
        raise ValueError('Unsupported review kind: '+kind)
    if kind=='checked_root_vowels' and 'безударная проверяемая гласная корня' not in card['question']:
        raise ValueError('Instruction does not match root classification: '+card['number'])
    selected=[];blocks=[]
    for index,(row,template) in enumerate(zip(review['rows'],rows),1):
        if row['number']!=index:raise ValueError('Row numbers must match source order')
        patterns=template.split(',')
        if len(patterns)!=len(row['words']):raise ValueError('Word count mismatch')
        if kind=='checked_root_vowels':
            originals=[re.sub(r'\([^)]*\)','',html.unescape(re.sub('<[^>]*>','',p))).strip() for p in patterns]
            if originals!=row['words']:raise ValueError('Review words differ from source row')
            kinds=row['classifications']
            if len(kinds)!=len(originals) or any(k not in {'checked','alternating','dictionary'} for k in kinds):
                raise ValueError('Invalid root classifications')
            fits=all(k=='checked' for k in kinds)
            if fits:selected.append(str(row['number']))
            blocks.append(f"<b>Ряд {row['number']}{' — подходит' if fits else ' — не подходит'}.</b> "+html.escape(row['reason']))
            continue
        completed=[];letters=[]
        for pattern,word in zip(patterns,row['words']):
            bare=re.sub(r'\([^)]*\)','',html.unescape(re.sub('<[^>]*>','',pattern))).strip()
            parts=re.split(r'\.{2,}',bare)
            if len(parts)!=2:raise ValueError('Expected one letter gap: '+bare)
            match=re.fullmatch(re.escape(parts[0])+r'(.)'+re.escape(parts[1]),word,re.I)
            if not match:raise ValueError(f'Word does not fit {bare}: {word}')
            letter=match[1];letters.append(letter.upper())
            at=len(parts[0]);completed.append(html.escape(word[:at])+'<b>'+html.escape(letter)+'</b>'+html.escape(word[at+1:]))
        fits=len(set(letters))==1
        if fits:selected.append(str(row['number']))
        blocks.append(f"<b>Ряд {row['number']}{' — подходит' if fits else ' — не подходит'}.</b> "+', '.join(completed)+'. Пропущенные буквы: '+', '.join(letters)+'. '+html.escape(row['reason']))
    answer=''.join(selected)
    if answer!=card['answer'] or ''.join('1'if str(i+1)in selected else'0'for i in range(len(rows)))!=card['answer_verify']:
        raise ValueError('Editorial row selection disagrees with historically checked answer: '+card['number'])
    intro=('Слова уже написаны полностью. Выбираем ряды, где в каждом слове есть безударная гласная корня, которую можно проверить ударением. Чередующееся или словарное написание не подходит. Знак ударения в проверочном слове показывает, какую гласную проверяем.<br><br>' if kind=='checked_root_vowels' else '')
    return 'Верно: '+', '.join(selected)+'.<br><br>'+intro+'<br><br>'.join(blocks)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');parser.add_argument('--group',choices=['prefix','roots'],default='prefix');args=parser.parse_args()
    registry='root_card_reviews.json' if args.group=='roots' else 'prefix_card_reviews.json'
    batch=json.loads((ROOT/'data/knowledge'/registry).read_text());reviews=batch['cards']
    log_path=ROOT/'docs/content-audit/explanation-reviews.json'
    log=json.loads(log_path.read_text())
    prepared=[]
    for review in reviews:
        path=ROOT/'data'/f"card_{review['id']}.json";card=json.loads(path.read_text());expected=render(card,review)
        if card['explanation']==expected:continue
        if not args.write:raise ValueError('Explanation differs from reviewed rows: '+review['id'])
        before=card['explanation'];card['explanation']=expected
        prepared.append((path, json.dumps(card,ensure_ascii=False,indent=2)+'\n'))
        reason=('Классификация гласных в готовых словах: разбор всех пяти рядов, без вымышленных пропусков и заглавных букв внутри слов. Ударение указано в проверочных словах.' if review.get('kind')=='checked_root_vowels' else 'Все пять рядов восстановлены по явно проверенным словам; каждая буква сопоставлена пропуску.')
        log['reviews'].append({'changeId':('ROOT-' if args.group=='roots' else 'PREFIX-')+review['id'],'id':review['id'],'reviewer':'assistant','reviewDate':batch.get('reviewDate','2026-10-27'),'status':review['status'],'reason':reason+' Выбор рядов совпал с answer и answer_verify. Источник: Лопатин (ред.), Эксмо, 2007; см. '+registry+'.','answerUnchanged':True,'previousExplanationSha256':hashlib.sha256(before.encode()).hexdigest(),'explanationSha256':hashlib.sha256(expected.encode()).hexdigest()})
    changed=len(prepared)
    if args.write and prepared:
        # Validate the complete batch before any mutation; keep the journal with the edits.
        writes=prepared+[(log_path,json.dumps(log,ensure_ascii=False,indent=2)+'\n')]
        snapshots={path:path.read_bytes() for path,_ in writes}
        try:
            for path,value in writes:path.write_text(value)
        except OSError:
            for path,value in snapshots.items():path.write_bytes(value)
            raise
    print(f'Explanations checked: {len(reviews)}; updated: {changed}')


if __name__=='__main__':main()
