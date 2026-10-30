"""Validate the complete word inventory against production stress cards."""
import re


def normalize(value):
    return re.sub(r'\([^)]*\)', '', value).strip().lower().replace('ё', 'е')


def validate_glossary(data, cards, mapping, plain):
    inventory = {}
    stress_cards = [card for card in cards if mapping(card)['task']==4]
    for card in stress_cards:
        for variant in card['variants']:
            inventory.setdefault(normalize(plain(variant)), set()).add(card['number'])
    words = {w['id']:w for w in data['words']}
    if len(words)!=len(data['words']) or set(words)!=set(inventory):
        raise ValueError('Stress glossary must cover every word form from every stress option exactly once')
    for wid, entry in words.items():
        form = entry['form']
        if (not re.fullmatch('[А-ЯЁа-яё]+', form) or normalize(form)!=wid or
            len(re.findall('[АЕЁИОУЫЭЮЯ]', form))!=1 or
            any(c.isupper() and c not in 'АЕЁИОУЫЭЮЯ' for c in form) or
            entry['cardIds']!=sorted(inventory[wid])):
            raise ValueError('Invalid stress form or card inventory: '+wid)
    grouped, group_ids, part_ids = [], [], []
    for part in data['parts']:
        part_ids.append(part['id'])
        for group in part['groups']:
            group_ids.append(group['id'])
            if not group['wordIds']:
                raise ValueError('Empty stress comparison group')
            grouped.extend(group['wordIds'])
    if (set(grouped)!=set(words) or len(grouped)!=len(words) or
        len(set(group_ids))!=len(group_ids) or len(set(part_ids))!=len(part_ids) or
        data['wordCount']!=len(words) or data['cardCount']!=len(stress_cards)):
        raise ValueError('Incomplete or duplicated stress grouping')
    return data


def glossary_text(data):
    words = {word['id']:word for word in data['words']}
    lines = [data['title'], f"Словоформ: {data['wordCount']}. Заданий: {data['cardCount']}.",
             'Заглавная гласная обозначает ударение. Сравнивайте каждую конкретную форму.', '']
    for part in data['parts']:
        lines.extend([part['title'].upper(), ''])
        for group in part['groups']:
            lines.append(group['title'])
            lines.append(' — '.join(words[wid]['form'] +
                         (' ('+words[wid]['context']+')' if words[wid].get('context') else '')
                         for wid in group['wordIds']))
            if group.get('note'):
                lines.append(group['note'])
            lines.append('')
    return '\n'.join(lines)
