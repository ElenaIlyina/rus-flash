#!/usr/bin/env python3
"""Reproduce source-linked row explanations for reviewed spelling exercises.

Default: check only. --write updates explanations and appends immutable review records.
Does not change answers, source questions, or variants. Word forms are editorial data,
not guessed by the script. Mechanical validation is not full teacher acceptance.
"""
import sys
from pathlib import Path as _ProjectPath
sys.path.insert(0,str(_ProjectPath(__file__).resolve().parents[2]/'scripts'))
import argparse
import hashlib
import html
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]


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
    if kind not in {'same_letter_gap','same_letter_word_pair','target_letter_word','checked_root_vowels','checked_root_gaps','alternating_root_vowels','alternating_root_gaps','target_root_word'}:
        raise ValueError('Unsupported review kind: '+kind)
    if kind in {'checked_root_vowels','checked_root_gaps'} and 'безударная проверяемая гласная корня' not in card['question']:
        raise ValueError('Instruction does not match root classification: '+card['number'])
    root_target = kind == 'target_root_word'
    root_category = ('alternating' if kind.startswith('alternating_root_') else
                     review.get('targetRoot') if root_target else 'checked')
    if kind.startswith('alternating_root_') or root_target:
        descriptor = {'checked': 'проверяемая', 'alternating': 'чередующаяся'}.get(root_category)
        if descriptor is None or f'безударная {descriptor} гласная корня' not in card['question']:
            raise ValueError('Instruction does not match target root classification')
        if root_target and 'выпишите это слово' not in card['question'].lower():
            raise ValueError('Root-word exercise does not match instruction')
    word_pair = kind == 'same_letter_word_pair'
    target_word = kind == 'target_letter_word'
    target = None
    if target_word:
        instruction = html.unescape(re.sub('<[^>]*>', '', card['question']))
        match = re.search(r'буква\s+([А-ЯЁ])', instruction, re.I)
        if not match or 'выпишите слово' not in instruction.lower():
            raise ValueError('Target-letter review does not match instruction')
        target = match[1].upper()
    if word_pair and 'выпишите эти слова' not in card['question'].lower():
        raise ValueError('Word-pair review does not match instruction')
    selected=[];blocks=[]
    for index,(row,template) in enumerate(zip(review['rows'],rows),1):
        if row['number']!=index:raise ValueError('Row numbers must match source order')
        patterns=template.split(',')
        if len(patterns)!=len(row['words']):raise ValueError('Word count mismatch')
        if kind in {'checked_root_vowels','alternating_root_vowels'}:
            originals=[re.sub(r'\([^)]*\)','',html.unescape(re.sub('<[^>]*>','',p))).strip() for p in patterns]
            if originals!=row['words']:raise ValueError('Review words differ from source row')
            kinds=row['classifications']
            if len(kinds)!=len(originals) or any(k not in {'checked','alternating','dictionary','stressed_root'} for k in kinds):
                raise ValueError('Invalid root classifications')
            fits=all(k==root_category for k in kinds)
            if fits:selected.append(str(row['number']))
            blocks.append(f"<b>Ряд {row['number']}{' — подходит' if fits else ' — не подходит'}.</b> "+html.escape(row['reason']))
            continue
        if (target_word or root_target) and len(patterns) != 1:
            raise ValueError('Target-letter exercises require one word per option')
        if word_pair and len(patterns) != 2:
            raise ValueError('Word-pair exercises require two words in every row')
        widths = row.get('gapWidths', [1] * len(patterns))
        if len(widths) != len(patterns) or any(type(n) is not int or n not in (0, 1) for n in widths):
            raise ValueError('Invalid explicit gap widths')
        completed=[];letters=[]
        for part_index,(pattern,word,width) in enumerate(zip(patterns,row['words'],widths),1):
            bare=re.sub(r'\([^)]*\)','',html.unescape(re.sub('<[^>]*>','',pattern))).strip()
            if '\u0301' not in word:
                bare=bare.replace('\u0301', '')
            for glyph in row.get('accentGlyphs', []):
                if glyph.get('part') != part_index:
                    continue
                if (glyph.get('from'), glyph.get('to')) != ('á', 'а') or bare.count('á') != 1:
                    raise ValueError('Unsupported explicit accent glyph normalization')
                bare=bare.replace('á', 'а')
            parts=re.split(r'\.{2,}',bare)
            if len(parts)!=2:raise ValueError('Expected one letter gap: '+bare)
            match=re.fullmatch(re.escape(parts[0])+(r'(.)' if width else r'()')+re.escape(parts[1]),word,re.I)
            if not match:raise ValueError(f'Word does not fit {bare}: {word}')
            letter=match[1];letters.append(letter.upper())
            at=len(parts[0])
            completed.append(html.escape(word[:at])+'<b>'+html.escape(letter)+'</b>'+html.escape(word[at+width:]))
        if kind in {'checked_root_gaps','alternating_root_gaps','target_root_word'}:
            kinds=row['classifications']
            if len(kinds)!=len(patterns) or any(k not in {'checked','alternating','dictionary'} for k in kinds):
                raise ValueError('Invalid gap classifications')
            fits=all(k==root_category for k in kinds)
        elif target_word:
            fits=letters==[target]
        else:
            fits=all(letters) and len(set(letters))==1
        if fits:selected.append(str(row['number']))
        label='Слово' if target_word or root_target else 'Ряд'
        blocks.append(f"<b>{label} {row['number']}{' — подходит' if fits else ' — не подходит'}.</b> "+', '.join(completed)+'. Пропущенные буквы: '+', '.join(letter or 'буква не вставляется' for letter in letters)+'. '+html.escape(row['reason']))
    answer=''.join(selected)
    if word_pair or target_word or root_target:
        if len(selected) != 1:
            raise ValueError('Word exercise must have exactly one matching row')
        answer=' '.join(review['rows'][int(selected[0])-1]['words'])
        canonical=lambda value: re.sub(r'\s+', ' ', value.strip()).casefold().replace('ё', 'е')
        matches=canonical(answer)==canonical(card['answer'])==canonical(card['answer_verify'])
    else:
        matches=answer==card['answer'] and ''.join('1'if str(i+1)in selected else'0'for i in range(len(rows)))==card['answer_verify']
    if not matches:
        raise ValueError('Editorial row selection disagrees with historically checked answer: '+card['number'])
    intro=('Слова уже написаны полностью. Выбираем ряды, где в каждом слове есть безударная гласная корня, которую можно проверить ударением. Чередующееся или словарное написание не подходит. Знак ударения в проверочном слове показывает, какую гласную проверяем.<br><br>' if kind=='checked_root_vowels' else '')
    if kind=='checked_root_gaps':intro='Восстановим слова и для каждой вставленной гласной определим способ проверки. Подходит ряд, в котором все три гласные корня проверяются ударением; сами буквы могут быть разными. Проверочное слово должно сохранять значение корня.<br><br>'
    intro = review.get('intro', intro)
    lead = ('Ответ: '+html.escape(answer)+'.' if target_word or root_target else
            'Ответ: '+html.escape(answer)+'. Выбираем ряд '+selected[0]+'.' if word_pair else
            'Верно: '+', '.join(selected)+'.')
    return lead+'<br><br>'+intro+'<br><br>'.join(blocks)


def validate_rule_evidence(review, paragraphs):
    """Reject stale or incomplete source fingerprints for rewritten rows."""
    if not review.get("rewriteReview"):
        return
    for row in review["rows"]:
        expected = row["sourceIds"]
        evidence = row.get("sourceEvidence", [])
        if not expected or len(set(expected)) != len(expected):
            raise ValueError("Missing or duplicate rule references: " + review["id"])
        if len(evidence) != len(expected) or {r.get("sourceId") for r in evidence} != set(expected):
            raise ValueError("Incomplete rule evidence: " + review["id"])
        for ref in evidence:
            paragraph = paragraphs.get(ref["sourceId"])
            if paragraph is None or ref.get("textSha256") != paragraph["textSha256"]:
                raise ValueError("Stale rule evidence: " + review["id"])
            if ref.get("method") != "paragraph_text_read":
                raise ValueError("Unsupported rule evidence method: " + review["id"])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');parser.add_argument('--group',choices=['prefix','roots','suffixes','verbs'],default='prefix');args=parser.parse_args()
    registry={'prefix':'prefix_card_reviews.json','roots':'root_card_reviews.json','suffixes':'suffix_card_reviews.json','verbs':'verb_card_reviews.json'}[args.group]
    batch=json.loads((ROOT/'dev/data/knowledge'/registry).read_text());reviews=batch['cards']
    log_path=ROOT/'dev/docs/content-audit/explanation-reviews.json'
    log=json.loads(log_path.read_text())
    prepared=[]
    for review in reviews:
        path=ROOT/'data'/f"card_{review['id']}.json";card=json.loads(path.read_text());expected=render(card,review)
        if card['explanation']==expected:continue
        if not args.write:raise ValueError('Explanation differs from reviewed rows: '+review['id'])
        before=card['explanation'];card['explanation']=expected
        prepared.append((path, json.dumps(card,ensure_ascii=False,indent=2)+'\n'))
        reason=('Классификация гласных в готовых словах: разбор всех пяти рядов, без вымышленных пропусков и заглавных букв внутри слов. Ударение указано в проверочных словах.' if review.get('kind')=='checked_root_vowels' else 'Все пять рядов восстановлены по явно проверенным словам; каждая буква сопоставлена пропуску.')
        log['reviews'].append({'changeId':{'roots':'ROOT-','prefix':'PREFIX-','suffixes':'SUFFIX-','verbs':'VERB-'}[args.group]+review['id'],'id':review['id'],'reviewer':'assistant','reviewDate':review.get('rewriteReview',{}).get('date',batch.get('reviewDate','2026-10-27')),'status':review['status'],'reason':review.get('reviewReason',reason)+' Выбор рядов совпал с answer и answer_verify. Источник: Лопатин (ред.), Эксмо, 2007; см. '+registry+'.','answerUnchanged':True,'previousExplanationSha256':hashlib.sha256(before.encode()).hexdigest(),'explanationSha256':hashlib.sha256(expected.encode()).hexdigest()})
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
