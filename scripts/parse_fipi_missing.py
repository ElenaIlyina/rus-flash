#!/usr/bin/env python3
"""Download missing EGE cards from FIPI and save them as data/card_XXXXXX.json.

Reads data/fipi_numbers.txt (all 2040 ids), skips cards already present in
data/card_*.json, fetches the FIPI question pages, and writes the raw card data
(question, KES, variants, guid) into fresh JSON files. Answer fields are left
empty (answers are added later in semi-manual mode / via solve.php).

Usage:
    python3 scripts/parse_fipi_missing.py            # fetch all missing
    python3 scripts/parse_fipi_missing.py --limit 20 # only first 20 missing
    python3 scripts/parse_fipi_missing.py --csv report.csv
"""
import glob
import html
import json
import os
import re
import sys
import urllib.request
import urllib.parse
import http.cookiejar
import ssl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')
PROJ = 'AF0ED3F2557F8FFC4C06F80B6803FD26'
BASE = 'https://ege.fipi.ru/bank/questions.php'
PAGES = 23  # 22 pages x 100 cards ~ 2200 > 2040


def clean(text):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text or ''))).strip()


def make_opener():
    ctx = ssl.create_default_context()
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPCookieProcessor(jar),
    )
    return opener


def fetch_pages(opener):
    pages = {}
    # single big page: FIPI caps out at ~2200 cards; pagesize=3000 returns all
    # at once (old per-100 pagination silently dropped cards whose ids are not
    # all-uppercase, so a page-index-based loop is obsolete anyway)
    url = f'{BASE}?proj={PROJ}&page=1&pagesize=3000'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        raw = opener.open(req).read()
        for enc in ('utf-8', 'cp1251'):
            try:
                pages[1] = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            pages[1] = raw.decode('cp1251', errors='ignore')
        print(f'  page 1 (pagesize=3000): {len(pages[1])} bytes', flush=True)
    except Exception as e:
        print(f'  page 1: ERROR {e}', flush=True)
    return pages


def parse_card(seg, cid):
    out = {
        'number': cid,
        'guid': '',
        'kes': [],
        'question': '',
        'text': '',
        'variants': [],
        'answer': '',
        'answer_verify': '',
        'explanation': '',
    }

    g = re.search(r'name="guid" value="([^"]+)"', seg)
    if g:
        out['guid'] = g.group(1)

    k = re.search(r'<td class="param-name">КЭС:</td><td class="param-row">(.*?)</td>', seg, re.DOTALL)
    if k:
        for dv in re.findall(r'<div>(.*?)</div>', k.group(1), re.DOTALL):
            t = clean(dv)
            if t:
                out['kes'].append(t)

    q = re.search(r"class='cell_0'>(.*?)</TD>", seg, re.DOTALL)
    if q:
        out['question'] = clean(q.group(1))

    # stimulus / source text for text-analysis tasks (22-27): the first qblock
    # carries the "<div id='hint'>Прочитайте текст...</div>" instruction plus the
    # source text as <p class=MsoNormal> paragraphs. The question block (cell_0 /
    # second qblock) only references sentence numbers, so without this the card
    # is unusable. Capture hint + paragraphs.
    txt_blocks = []
    for qb in re.finditer(r"<div class=\"qblock\">(.*?)(?:</div>\s*)?<div class=\"qblock\"", seg, re.DOTALL):
        body = qb.group(1)
        hint = re.search(r'name="hint">(.*?)</div>', body, re.DOTALL)
        if hint and 'Прочитайте' in hint.group(1):
            paras = [clean(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', body, re.DOTALL | re.IGNORECASE)]
            paras = [p for p in paras if p and p != '\xa0']
            parts = [clean(hint.group(1))] + paras
            text = '\n'.join(parts).strip()
            if text:
                txt_blocks.append(text)
            break
    if txt_blocks:
        out['text'] = txt_blocks[0]


    # variants only for checkbox "Выбор ответов" cards
    t = re.search(r'<td class="param-name">Тип ответа:</td><td>(.*?)</td>', seg, re.DOTALL)
    atype = t.group(1).strip() if t else ''
    if atype == 'Выбор ответов из предложенных вариантов':
        dm = re.search(r'class="distractors-table">(.*?)</table>', seg, re.DOTALL)
        if dm:
            for r in re.findall(r"<tr\s+class='active-distractor'>(.*?)</tr>", dm.group(1), re.DOTALL):
                tm = re.search(r'<p[^>]*>(.*?)</p>', r, re.DOTALL)
                out['variants'].append(clean(tm.group(1)) if tm else clean(r))

    return out


def main():
    args = sys.argv[1:]
    limit = None
    for i, a in enumerate(args):
        if a == '--limit' and i + 1 < len(args):
            limit = int(args[i + 1])

    with open(os.path.join(DATA_DIR, 'fipi_numbers.txt'), encoding='utf-8') as f:
        all_ids = [ln.strip().upper() for ln in f if ln.strip()]

    have = {os.path.basename(jf)[5:-5].upper()
            for jf in glob.glob(os.path.join(DATA_DIR, 'card_*.json'))}
    all_missing = [i for i in all_ids if i not in have]

    print('fetching pages...')
    opener = make_opener()
    pages = fetch_pages(opener)

    seg_index = {}
    for page, h in pages.items():
        # ids are NOT always uppercase on fiPI (e.g. 8e3e38, BeAc67) — match
        # case-insensitively and normalise to upper for filenames
        for m in re.finditer(r"id='q([0-9A-Fa-f]{6})'", h):
            cid = m.group(1).upper()
            pos = m.start()
            if cid in all_missing:
                seg_index[cid] = h[pos:pos + 15000]

    # missing cards that DID appear on pages -> fetch them
    available = [i for i in all_missing if i in seg_index]
    # not on any page -> won't be fetched, report separately
    unavailable = [i for i in all_missing if i not in seg_index]

    if limit:
        available = available[:limit]
        print(f'limiting to first {limit}')

    print(f'total ids: {len(all_ids)}, already have: {len(have)}, '
          f'to fetch: {len(available)}, not on pages: {len(unavailable)}')

    created = 0
    for cid in available:
        seg = seg_index[cid]
        card = parse_card(seg, cid)
        path = os.path.join(DATA_DIR, f'card_{cid}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(card, f, ensure_ascii=False, indent=2)
        created += 1
        print(f'  {cid}: saved (kes={len(card["kes"])}, vars={len(card["variants"])})', flush=True)

    # persist the not-found report
    if unavailable:
        nf_path = os.path.join(DATA_DIR, 'fipi_not_found.txt')
        with open(nf_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(unavailable) + '\n')
        print(f'wrote {len(unavailable)} unavailable ids -> {nf_path}')

    print(f'done: created {created} cards')


if __name__ == '__main__':
    main()
