#!/usr/bin/env python3
"""Save every EGE card from the FIPI bank as one JSON file.

No HTML parsing: each card is written as { number, guid, fetched_at, url, html }
where `fetched_at` is the export timestamp, `url` is the source page URL (or
file:// path when reading --page), and `html` is the raw qblock markup
(question, variants, answer form, task-info) exactly as the server returned
it. Shared passages outside identified qblocks are currently NOT preserved.
Saved for future development; no new collection is needed for the received bank.

Usage:
    python3 dev/scripts/fetch_fipi_cards_raw.py --limit 10          # first 10 codes.txt ids
    python3 dev/scripts/fetch_fipi_cards_raw.py --all               # all ids from codes.txt
    python3 dev/scripts/fetch_fipi_cards_raw.py --ids 9273A5,011D96 # explicit ids
    python3 dev/scripts/fetch_fipi_cards_raw.py --out src/cards     # output directory
    python3 dev/scripts/fetch_fipi_cards_raw.py --page PATH.html    # reuse a saved bank page
"""
import json
import os
import re
import sys
import urllib.request
import http.cookiejar
import ssl
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJ = 'AF0ED3F2557F8FFC4C06F80B6803FD26'
BASE = 'https://ege.fipi.ru/bank/questions.php'
DEFAULT_OUT = os.path.join(ROOT, 'dev', 'generated', 'fipi-raw', 'cards')
CODES_FILE = os.path.join(ROOT, 'dev', 'data', 'fipi_numbers.txt')

QPATCH = re.compile(r"<div class=\"qblock[^\"]*\"[^>]*>")


def bank_url():
    return f'{BASE}?proj={PROJ}&page=1&pagesize=3000'


def fetch_page():
    ctx = ssl.create_default_context()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    url = bank_url()
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    raw = opener.open(req, timeout=180).read()
    for enc in ('utf-8', 'cp1251'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('cp1251', errors='ignore')


def split_cards(page):
    """Return {(UPPER_ID): raw_html} for every qblock that has an id."""
    starts = [m.start() for m in QPATCH.finditer(page)]
    ends = starts[1:] + [len(page)]
    out = {}
    for s, e in zip(starts, ends):
        raw = page[s:e]
        m = re.search(r"id='q([0-9A-Fa-f]{6})'", raw[:400])
        if m:
            out[m.group(1).upper()] = raw
    return out


def build_card(cid, raw, fetched_at, url):
    g = re.search(r'name="guid" value="([^"]+)"', raw)
    return {
        'number': cid,
        'guid': g.group(1) if g else '',
        'fetched_at': fetched_at,
        'url': url,
        'html': raw,
    }


def main():
    args = sys.argv[1:]
    limit = None
    ids = None
    out_dir = DEFAULT_OUT
    page_file = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1]); i += 2; continue
        if a == '--all':
            i += 1; continue
        if a == '--ids' and i + 1 < len(args):
            ids = [x.strip().upper() for x in args[i + 1].split(',') if x.strip()]
            i += 2; continue
        if a == '--out' and i + 1 < len(args):
            out_dir = args[i + 1]; i += 2; continue
        if a == '--page' and i + 1 < len(args):
            page_file = args[i + 1]; i += 2; continue
        i += 1

    if page_file:
        page = open(page_file, encoding='utf-8').read()
        source_url = Path(page_file).resolve().as_uri()
    else:
        print('fetching bank page...', flush=True)
        page = fetch_page()
        source_url = bank_url()
        print(f'  {len(page)} bytes', flush=True)

    fetched_at = datetime.now().astimezone().isoformat(timespec='seconds')

    by_id = split_cards(page)
    print(f'parsed {len(by_id)} cards', flush=True)

    want = ids
    if want is None:
        with open(CODES_FILE, encoding='utf-8') as f:
            want = [ln.strip().upper() for ln in f if ln.strip()]
        if limit:
            want = want[:limit]

    missing = [x for x in want if x not in by_id]
    if missing:
        print(f'WARN: not found on page: {missing}', file=sys.stderr)

    os.makedirs(out_dir, exist_ok=True)
    n = 0
    for cid in want:
        if cid not in by_id:
            continue
        card = build_card(cid, by_id[cid], fetched_at, source_url)
        with open(os.path.join(out_dir, f'card_{cid}.json'), 'w', encoding='utf-8') as f:
            json.dump(card, f, ensure_ascii=False, indent=2)
        n += 1
    print(f'done: {n} cards -> {out_dir}')


if __name__ == '__main__':
    main()
