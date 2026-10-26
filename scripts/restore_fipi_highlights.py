#!/usr/bin/env python3
"""Восстановление разметки FIPI (<b>/<u>/<sub>/<sup>) в поле text карт.

Строит по странице банка (questions.php pagesize=3000, кэш в /tmp/opencode)
словарь «параграф без разметки -> параграф с разметкой» (только p с <b>/<u>),
для каждой карты data/card_*.json с непустым text построчно сопоставляет
её абзацы с индексом и при полном покрытии записывает text с разметкой.

Usage:
    python3 scripts/restore_fipi_highlights.py                # все карты
    python3 scripts/restore_fipi_highlights.py --dry          # отчёт без записи
    python3 scripts/restore_fipi_highlights.py --ids 0ABFEC --dry
"""
import argparse
import glob
import html
import http.cookiejar
import json
import re
import ssl
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
PROJ = 'AF0ED3F2557F8FFC4C06F80B6803FD26'
BANK = 'https://ege.fipi.ru/bank/questions.php'
CACHE = Path('/tmp/opencode/fipi_bank.html')

KEEP = ('b', 'u', 'i', 'sub', 'sup')
TAG = re.compile(r'</?\s*([a-zA-Z]+)[^>]*>')


def norm(s):
    s = s.replace('\xa0', ' ').replace('\u200b', '')
    return re.sub(r'\s+', ' ', s).strip()


def strict(s):
    s = norm(s)
    return re.sub(r'\s+([,.:;!?")])', r'\1', s)


def keys(s):
    plain = strip_markup(s)
    return (plain, norm(plain), strict(plain))


def strip_markup(s):
    return re.sub(r'</?(?:%s)[^>]*>' % '|'.join(KEEP), '', s)


def clean_para(raw):
    t = re.sub(r'<br\s*/?>', '\n', raw, flags=re.I)
    t = re.sub(r'</?\s*(?:a|span|script)\b[^>]*>', '', t, flags=re.I)
    t = TAG.sub(lambda m: '<%s%s>' % ('/' if m.group(0)[1] == '/' else '',
                                      m.group(1).lower())
                if m.group(1).lower() in KEEP else '', t)
    t = html.unescape(t)
    t = re.sub(r'<i(?:\s[^>]*)?>[\s\xa0]*</i>', '', t, flags=re.I)
    t = re.sub(r'[ \t]*\n[ \t]*', '\n', t)
    t = re.sub(r'(</?b|u|i|sub|sup) +', r'\1', t)
    t = re.sub(r'\n +', '\n', t)
    t = re.sub(r' {2,}', ' ', t)
    return t.strip()


def has_markup(raw):
    return re.search(r'<(?:[ubi]\b)', raw) is not None


def is_shouty_italic(t):
    """Весь абзац курсивом (или пустой курсив) — оформление, не выделение."""
    non_i = re.sub(r'<i(?:\s[^>]*)?>.*?</i>|<i(?:\s[^>]*)?>|</i>',
                   '', t, flags=re.DOTALL | re.I)
    return len(re.sub(r'<[^>]+>', '', non_i).replace('\xa0', ' ').strip()) < 3


def paras_index(page):
    idx = {}
    for raw in re.findall(r'<p\b[^>]*>(.*?)</p>', page, re.DOTALL | re.I):
        if not has_markup(raw):
            continue
        t = clean_para(raw)
        if not t or is_shouty_italic(t):
            continue
        for key in keys(t):
            idx.setdefault(key, t)
    return idx


def fetch_bank():
    if CACHE.exists() and CACHE.stat().st_size > 1_000_000:
        page = CACHE.read_text(encoding='utf-8')
        if 'guid' in page:
            return page
    ctx = ssl.create_default_context()
    op = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    req = urllib.request.Request(
        f'{BANK}?proj={PROJ}&page=1&pagesize=3000',
        headers={'User-Agent': 'Mozilla/5.0'})
    raw = op.open(req, timeout=120).read()
    for enc in ('utf-8', 'cp1251'):
        try:
            page = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        page = raw.decode('cp1251', 'ignore')
    CACHE.write_text(page, encoding='utf-8')
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true', help='не сохранять правки')
    ap.add_argument('--ids', help='только эти карты (через запятую)')
    args = ap.parse_args()

    page = fetch_bank()
    print(f'банк: {len(page)//1024} KB', flush=True)
    tidx = paras_index(page)
    print(f'параграфов с <u> в индексе: {len(tidx)}', flush=True)

    wanted = None
    if args.ids:
        wanted = [x.strip().upper() for x in args.ids.split(',') if x.strip()]

    updated = same = 0
    for jf in sorted(glob.glob(str(DATA / 'card_*.json'))):
        c = json.loads(Path(jf).read_text(encoding='utf-8'))
        if not (c.get('text') or '').strip():
            continue
        tid = (c.get('number') or '').strip().upper()
        if wanted and tid not in wanted:
            continue
        lines = [p.strip() for p in c['text'].split('\n') if p.strip()]
        mapped = []
        for line in lines:
            hit = None
            for key in keys(line):
                hit = tidx.get(key)
                if hit:
                    break
            mapped.append(hit or line)
        new_markup = '\n'.join(mapped)
        if new_markup == c['text']:
            same += 1
            continue
        n_changed = sum(a != b for a, b in zip(mapped, lines))
        if not args.dry:
            c['text'] = new_markup
            Path(jf).write_text(json.dumps(c, ensure_ascii=False, indent=2),
                                encoding='utf-8')
        n_u = len(re.findall(r'<u(?:\s[^>]*)?>', new_markup))
        print(f'UPD {tid}: абз. {len(lines)}, заменено {n_changed}, <u>: {n_u}',
              flush=True)
        updated += 1

    print(f'\nитог: обновлено {updated}, без изменений {same}, '
          f'без соответствия: пропущено {updated and 0 or 0}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
