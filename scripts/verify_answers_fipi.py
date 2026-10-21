#!/usr/bin/env python3
"""Проверка ответов карт через FIPI solve.php (fipi_notes.md).

Сессия: GET questions.php (куки) -> POST solve.php {guid, answer, ajax=1, proj}.
Ответ: '3' верно / '2' неверно / прочее — ошибка.

Режимы:
  --tasks 7 8        все карты выбранных заданий (по html/cards_manifest.js)
  --ids 729EAA,...   конкретные карты (UPPER CASE, через запятую)
  --file ids.txt     по одному ID на строку
По умолчанию: сверяет answer из data/card_<ID>.json с FIPI и печатает отчёт.
С ответом '--ans СЛОВО' подставляет указанный ответ вместо data (пере-проверка альтернатив).
"""
import argparse
import http.cookiejar
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJ = 'AF0ED3F2557F8FFC4C06F80B6803FD26'
INIT_URL = f'https://ege.fipi.ru/bank/questions.php?proj={PROJ}&page=1&pagesize=100'
SOLVE_URL = 'https://ege.fipi.ru/bank/solve.php'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def make_opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPCookieProcessor(cj),
    )


def fipi_check(op, guid, answer):
    data = urllib.parse.urlencode({
        'guid': guid, 'answer': answer, 'ajax': '1', 'proj': PROJ,
    }).encode()
    req = urllib.request.Request(SOLVE_URL, data=data, headers={
        'User-Agent': 'Mozilla/5.0',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': INIT_URL,
    })
    with op.open(req, timeout=15) as r:
        return r.read().decode('utf-8', 'ignore').strip()


def card_ids_for_tasks(tasks):
    manifest_path = ROOT / 'html' / 'cards_manifest.js'
    src = manifest_path.read_text(encoding='utf-8')
    m = re.search(r'"tasks"\s*:\s*\{(.*?)\n\s*\}', src, re.S)
    if not m:
        raise RuntimeError('в cards_manifest.js не найден блок "tasks"')
    ids = []
    for t in tasks:
        # каждая запись вида "7": ["03ADF2", ...]
        entry = re.search(r'"%s"\s*:\s*\[(.*?)\]' % re.escape(str(t)), m.group(1), re.S)
        if entry:
            ids.extend(re.findall(r'"([0-9A-F]+)"', entry.group(1)))
    return ids


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--tasks', help='задания через запятую, напр. 1,2,7')
    g.add_argument('--ids', help='ID карт через запятую')
    g.add_argument('--file', help='файл с ID карт (по одному на строку)')
    ap.add_argument('--ans', help='проверить указанный ответ вместо data/<ID>.answer')
    ap.add_argument('--sleep', type=float, default=0.15, help='пауза между запросами, сек')
    args = ap.parse_args()

    if args.tasks:
        ids = card_ids_for_tasks([t.strip() for t in args.tasks.split(',')])
    elif args.ids:
        ids = [x.strip().upper() for x in args.ids.split(',') if x.strip()]
    elif args.file:
        ids = [l.strip().upper() for l in Path(args.file).read_text().splitlines() if l.strip()]
    else:
        ap.error('нужен --tasks, --ids или --file')

    op = make_opener()
    op.open(urllib.request.Request(INIT_URL, headers={'User-Agent': 'Mozilla/5.0'})).read()

    ok = bad = fail = 0
    rejected = []
    for cid in ids:
        cpath = ROOT / 'data' / f'card_{cid}.json'
        if not cpath.exists():
            print(f'?? {cid}: нет файла data/card_{cid}.json')
            fail += 1
            continue
        card = json.loads(cpath.read_text(encoding='utf-8'))
        answer = (args.ans if args.ans is not None else (card.get('answer') or '')).strip()
        verify = (card.get('answer_verify') or '').strip()
        if not answer:
            answer = verify
        # choice-ответ FIPI принимает только битмаском (fipi_notes.md §4-5):
        if not args.ans and verify != answer and set(verify) <= {'0', '1'}:
            answer = verify
        # перечень ('134') конвертируем в битмаск; перестановки (длина = числу
        # вариантов, цифры без повторов) — как есть (§6).
        nvar = len(card.get('variants') or [])
        if (not args.ans and answer.isdigit() and set(answer) <= set('123456789')
                and answer == verify and nvar
                and not (len(answer) == nvar and len(set(answer)) == nvar)):
            answer = ''.join('1' if str(p + 1) in answer else '0' for p in range(nvar))
        if not answer:
            print(f'-- {cid}: пустой answer, пропуск')
            continue
        try:
            res = fipi_check(op, card['guid'], answer)
        except Exception as e:
            print(f'!! {cid}: ошибка запроса: {e}')
            fail += 1
            continue
        if res == '3':
            ok += 1
            print(f'OK   {cid} {answer!r}')
        elif res == '2':
            bad += 1
            rejected.append((cid, answer))
            print(f'FAIL {cid} {answer!r} — FIPI: неверно')
        else:
            fail += 1
            rejected.append((cid, answer))
            print(f'FAIL {cid} {answer!r} — FIPI: {res!r}')
        time.sleep(args.sleep)

    print(f'\nитого: карт {len(ids)}, верно {ok}, неверно {bad}, ошибок/пропусков {fail}')
    if rejected:
        print('не подтверждены:', ', '.join(f'{c}({a})' for c, a in rejected))
    return 0 if bad == 0 and fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
