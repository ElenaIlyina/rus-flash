#!/usr/bin/env python3
"""Reproduce source-linked row-by-row explanations for the 12 inspected prefix cards.

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
    rows=variants(card)
    if len(rows)!=len(review['rows']):raise ValueError('Row count mismatch: '+card['number'])
    selected=[];blocks=[]
    for row,template in zip(review['rows'],rows):
        patterns=template.split(',')
        if len(patterns)!=len(row['words']):raise ValueError('Word count mismatch')
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
    return 'Верно: '+', '.join(selected)+'.<br><br>'+'<br><br>'.join(blocks)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    reviews=json.loads((ROOT/'data/knowledge/prefix_card_reviews.json').read_text())['cards']
    log_path=ROOT/'docs/content-audit/explanation-reviews.json'
    log=json.loads(log_path.read_text())
    prepared=[]
    for review in reviews:
        path=ROOT/'data'/f"card_{review['id']}.json";card=json.loads(path.read_text());expected=render(card,review)
        if card['explanation']==expected:continue
        if not args.write:raise ValueError('Explanation differs from reviewed rows: '+review['id'])
        before=card['explanation'];card['explanation']=expected
        prepared.append((path, json.dumps(card,ensure_ascii=False,indent=2)+'\n'))
        log['reviews'].append({'changeId':'PREFIX-'+review['id'],'id':review['id'],'reviewer':'assistant','reviewDate':'2026-10-27','status':review['status'],'reason':'Все пять рядов восстановлены по явно проверенным словам; каждая буква сопоставлена пропуску, выбор рядов совпал с answer и answer_verify. Источник: Лопатин (ред.), Эксмо, 2007; см. prefix_card_reviews.json.','answerUnchanged':True,'previousExplanationSha256':hashlib.sha256(before.encode()).hexdigest(),'explanationSha256':hashlib.sha256(expected.encode()).hexdigest()})
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
    print(f'Prefix explanations checked: {len(reviews)}; updated: {changed}')


if __name__=='__main__':main()
