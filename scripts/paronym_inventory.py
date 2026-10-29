"""Complete, reproducible word-group inventory of the task 5 bank; stdlib only."""
import hashlib
import html
import json
import re
import unicodedata


def highlighted_words(value):
    text = unicodedata.normalize('NFC', html.unescape(re.sub(r'<[^>]+>', '', value)))
    return re.findall(r'\b[А-ЯЁ]{2,}(?:-[А-ЯЁ]{2,})*\b', text)


def inventory(cards, mapping, classify):
    groups = {g['id']:g for g in mapping['groups']}
    forms = {}
    for group in groups.values():
        for form in group['forms']:
            if form in forms: raise ValueError('Ambiguous paronym form: ' + form)
            forms[form] = group['id']
    ignored = {(r['cardId'],r['variant'],r['token']) for r in mapping['ignoredTokens']}
    rows, usage = [], {gid:set() for gid in groups}
    for card in cards:
        if classify(card)['task'] != 5: continue
        cid = card['number']
        options = []
        for position, value in enumerate(card.get('variants', []), 1):
            words = [w for w in highlighted_words(value) if (cid,position,w) not in ignored]
            if len(words) != 1: raise ValueError(f'Expected one highlighted paronym: {cid}, {position}')
            word = words[0]
            if word not in forms: raise ValueError(f'Unmapped paronym: {cid}, {word}')
            options.append({'position':position, 'form':word, 'groupId':forms[word]})
            usage[forms[word]].add(cid)
        answer = unicodedata.normalize('NFC', card['answer'].upper())
        if answer not in forms: raise ValueError('Unmapped paronym answer: ' + cid)
        usage[forms[answer]].add(cid)
        target = [o['position'] for o in options if o['groupId']==forms[answer]]
        if len(target) != 1: raise ValueError('Ambiguous answer group: ' + cid)
        rows.append({'id':cid, 'sourceSha256':hashlib.sha256(json.dumps(card,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
                     'options':options, 'answer':answer, 'answerGroupId':forms[answer], 'replacementPosition':target[0]})
    selected = [{k:v for k,v in group.items() if k!='forms'} | {'cardIds':sorted(usage[gid])}
                for gid,group in groups.items() if usage[gid]]
    selected.sort(key=lambda g:' / '.join(g['words']).replace('ё','е'))
    return {'schemaVersion':1, 'source':mapping['source'], 'cardCount':len(rows),
            'highlightedOccurrences':sum(len(r['options']) for r in rows), 'groups':selected, 'cards':rows}
