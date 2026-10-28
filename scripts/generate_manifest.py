#!/usr/bin/env python3
"""Legacy classifier retained for BEFORE/AFTER audit comparisons.

Shared extract_codes/load_cards helpers are reused by the current build.
The current position classifier is exam_2027.py, based on the official draft.
Optional CLI writes the historical cards_manifest.js for diagnostics only;
the website and FIPI verification utility no longer consume that manifest.
"""
import glob
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, 'data')
HTML_DIR = os.path.join(BASE, 'html')

# Kes code -> possible tasks, ordered: [default when code is alone, task when combined]
CODE_TASKS = {
    '3.2.3': [4],
    '3.3.3': [3],
    '3.5':   [7],            # 3.5.*
    '3.6':   [8],            # 3.6.*
    '3.7.2': [9],
    '3.7.3': [12],           # ъ/ь -> prefixes+ъ/ь cards belong to task 12 per editorial mapping
    '3.7.4': [10, 12],       # alone: prefixes (10); with 3.7.3: (12)
    '3.7.5': [11],
    '3.7.6': [15],
    '3.7.7': [13],
    '3.7.8': [14, 11],       # alone: (14); with 3.7.5: suffixes (11)
    '3.7.9': [14],
    '3.8.1': [16],
    '3.8.2': [21],
    '3.8.3': [16],
    '3.8.4': [16],
    '3.8.5': [17, 16],       # alone: obosoblennye (17); with other 3.8.*: punct analysis (16)
    '3.8.6': [18, 16],
    '3.8.7': [19, 16],
    '3.8.8': [20, 16],
    '3.8.9': [16],
    'общие': [16],           # "Общие положения" placeholder kes
    '1.2':   [2, 22],        # alone: means of connection (2); with 1.3/1.4: text analysis (22)
    '1.3':   [22],           # content compliance -> text analysis
    '1.4':   [22],           # info processing -> text analysis (sochinenie caught by question text)
    '1.5':   [27],           # plan/thesis/essay
    '2':     [1],            # functional stylistics (2.1..2.5 resolve here)
    '3.3.1': [3, 22, 23],    # alone: lexical meaning (3); with 3.3.2: speech types (23)
    '3.3.2': [23],           # functional-semantic speech types
}

# Keyword fallback over question text (checked when no Kes at all)
TASK_KEYWORDS = {
    1:  ['стилистическ', 'стиль речи', 'научный', 'публицистич', 'характеристики текста', 'характеристики фрагмента'],
    2:  ['самостоятельно подобрать', 'пропущенн', 'средства связи', 'связано с предыдущим'],
    3:  ['лексическое значение', 'многозначн', 'фразеологизм'],
    5:  ['пароним'],
    6:  ['плеоназм', 'тавтолог', 'исключить'],
    8:  ['грамматических ошибок'],
    9:  ['корн', 'череду'],
    14: ['слитно', 'дефисн', 'раздельно'],
    15: ['н и нн', '-нн-'],
    22: ['соответствуют содержанию', 'главная информация', 'утверждения являются верными'],
    23: ['типы речи', 'тип речи'],
    26: ['троп', 'рецензи', 'метафор', 'эпитет', 'выразительности'],
    27: ['напишите сочинение', 'сочинение-рассуждение'],
}


def extract_codes(card):
    codes = []
    for k in (card.get('kes') or []):
        k_low = k.lower()
        if 'общие' in k_low:
            codes.append('общие')
            continue
        m = re.match(r'\s*(\d(?:\.\d)*)', k)
        if m:
            codes.append(m.group(1))
    return codes


def resolve_code(code):
    """Map a Kes code like 3.5.2 to a CODE_TASKS key (longest prefix wins)."""
    if code in CODE_TASKS:
        return code
    parts = code.split('.')
    for n in range(len(parts) - 1, 0, -1):
        prefix = '.'.join(parts[:n])
        if prefix in CODE_TASKS:
            return prefix
    return None


def classify(card):
    """Return task number (1..27) or None if unclassifiable."""
    # essay cards: question text wins over KES (their KES span 1.2..1.5 + 2)
    q = card.get('question', '').lower()
    if 'напишите сочинение' in q or 'сочинение-рассуждение' in q:
        return 27

    # task 5 (paronyms) and task 21 (same punctuation rule) have signatures
    # that FIPI tags with KES of tasks 3 and 16/19 respectively — text wins
    if re.search(r'подобрав\s+к\s+выделенному\s+слову\s+пароним', q):
        return 5
    if re.search(r'(тире|двоеточие|запятая\(-ы[ея]\)|и тире).{0,120}одним и тем же правилом', q):
        return 21

    # tasks 24/25/26: FIPI tags them with the KES of tasks 2/3 (3.2.1/3.2.2,
    # 3.3.3/3.4.1, 1.2) — their formulations are distinctive, text wins over KES
    if re.search(r'выпишите\s+(один\s+)?(фразеологизм|антоним|синоним)', q):
        return 24
    if re.search(r'связа[но]+\s*\(-\s*ы\)?\s*с предыдущим при помощи', q) or \
            'с предыдущим при помощи' in q:
        return 25
    if 'список терминов' in q and re.search(r'\(а\)__', q):
        return 26

    keys = []
    for c in extract_codes(card):
        r = resolve_code(c)
        if r and r not in keys:
            keys.append(r)

    if keys:
        cand = [set(CODE_TASKS[k]) for k in keys]
        inter = set.intersection(*cand)
        if len(inter) == 1:
            return inter.pop()
        # ambiguous: use the default (first) task of the first known code
        return CODE_TASKS[keys[0]][0]

    # no kes -> keyword fallback on question text
    for t, kws in TASK_KEYWORDS.items():
        if any(kw in q for kw in kws):
            return t
    return None


def load_spec_names():
    names = {}
    p = os.path.join(DATA_DIR, 'ege_specification_mapping.json')
    try:
        spec = json.load(open(p, encoding='utf-8'))
        for t, info in spec.items():
            names[str(t)] = info.get('task_name', f'Задание {t}')
    except (OSError, ValueError):
        pass
    return names


def load_cards():
    cards = []
    for jf in sorted(glob.glob(os.path.join(DATA_DIR, 'card_*.json'))):
        with open(jf, encoding='utf-8') as f:
            cards.append(json.load(f))
    return cards


def build_manifest(cards, spec_names):
    tasks = {}
    for card in cards:
        t = classify(card)
        if t is None:
            print(f'WARNING: unclassified card {card.get("number")} (kes={card.get("kes")})',
                  file=sys.stderr)
            continue
        tasks.setdefault(str(t), []).append(card['number'])

    return {
        'total': len(cards),
        'generated': __import__('datetime').date.today().isoformat(),
        'task_names': spec_names,
        'tasks': {t: sorted(ids) for t, ids in sorted(tasks.items(), key=lambda kv: int(kv[0]))},
    }


def write_manifest(manifest):
    out = os.path.join(HTML_DIR, 'cards_manifest.js')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('// AUTO-GENERATED by scripts/generate_manifest.py - do not edit\n')
        f.write('// Regenerate: python3 scripts/generate_manifest.py\n')
        f.write('window.CARDS_MANIFEST = ')
        json.dump(manifest, f, ensure_ascii=False, indent=1)
        f.write(';\n')
    return out


def main():
    cards = load_cards()
    if not cards:
        print('No cards found in', DATA_DIR, file=sys.stderr)
        sys.exit(1)

    manifest = build_manifest(cards, load_spec_names())
    out = write_manifest(manifest)

    classified = sum(len(v) for v in manifest['tasks'].values())
    print(f'Manifest: {out}')
    print(f'  cards: {manifest["total"]}, classified: {classified}')
    for t, ids in manifest['tasks'].items():
        name = manifest['task_names'].get(t, '')
        print(f'  task {t:>2}: {len(ids):>4}  {name}')

if __name__ == '__main__':
    main()
