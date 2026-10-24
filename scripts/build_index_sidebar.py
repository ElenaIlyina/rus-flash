#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuilds the static sidebar in html/index.html from the classified card bank.

Groups cards by task number (ascending 1..27), then by KES inside each task.
Generates the same markup the existing JS expects (.kes-group/.kes-header/.item).
"""
import re
import sys
from collections import defaultdict

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import importlib.util

_spec = importlib.util.spec_from_file_location(
    'generate_manifest', __file__.rsplit('/', 1)[0] + '/generate_manifest.py')
gm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gm)

# The new index.html is handwritten; only rebuild the retained legacy navigator.
INDEX_PATH = __file__.rsplit('/', 1)[0] + '/../html/legacy.html'
START_MARK = '<div class="list" id="sidebarList">'
END_MARK = '    </div>\n    <div class="main">'


def _code_sort_key(kes):
    m = re.match(r'^([\d.]+)', kes)
    if not m:
        return (1, 0, ())
    parts = tuple(int(p) for p in m.group(1).rstrip('.').split('.'))
    return (0, 0, parts)


def shorten_kes(kes_key):
    parts = kes_key.split('<br>')
    if len(parts) > 1:
        codes = []
        for k in parts:
            m = re.match(r'^([\d.]+)', k.strip())
            codes.append(m.group(1).rstrip('.') if m else k.strip())
        return '; '.join(c for c in codes if c)
    k = parts[0].strip()
    m = re.match(r'^([\d.]+)?\.?\s*(.*)$', k)
    code = (m.group(1) or '').rstrip('.')
    name = (m.group(2) or '').strip()
    words = name.split()
    short = ' '.join(words[:5])
    if len(words) > 5:
        short += '…'
    shown = (code + ' ') if code else ''
    return (shown + short).strip()


def esc_attr(s):
    return s.replace('"', '&quot;')


def build_sidebar(cards):
    spec_names = gm.load_spec_names()
    groups = defaultdict(lambda: defaultdict(list))
    for c in cards:
        task = gm.classify(c)
        if not task:
            task = '0'
        kes_key = '<br>'.join(c.get('kes') or []) or 'Общие положения'
        groups[task][kes_key].append(c)

    out = []
    for task in sorted(groups, key=lambda t: int(t)):
        task_groups = groups[task]
        name = spec_names.get(task, '')
        for kes_key in sorted(task_groups, key=_code_sort_key):
            items = sorted(task_groups[kes_key], key=lambda c: c['number'])
            attr = esc_attr(kes_key)
            short = shorten_kes(kes_key)
            full_attr = esc_attr(kes_key.replace('<br>', '; '))
            title = f'№ {task}' if task != '0' else '№ ?'
            out.append(
                f'        <div class="kes-group collapsed" data-kes="{attr}" data-task="{task}">\n'
                f'            <div class="kes-header" onclick="toggleKes(this)" title="{full_attr}">\n'
                f'                <span><b>{title}</b> {short} '
                f"<span class='group-percent'>({len(items)})</span></span>\n"
                f'                <span class="arrow">▼</span>\n'
                f'            </div>\n'
                f'            <div class="kes-content">\n'
            )
            for c in items:
                cid = c['number']
                bt = f'№ {task}' if task != '0' else '№ ?'
                out.append(
                    f'                <div class="item" data-id="{cid}" data-task="{task}" '
                    f"onclick=\"loadCard('{cid}')\">\n"
                    f'                    <span class="num">{bt} · {cid}</span>\n'
                    f'                    <span class="badges"></span>\n'
                    f'                </div>\n'
                )
            out.append('            </div>\n        </div>\n')
    return ''.join(out).rstrip('\n')


def main():
    cards = gm.load_cards()
    sidebar_html = build_sidebar(cards)

    with open(INDEX_PATH, encoding='utf-8') as f:
        html = f.read()

    assert html.count(START_MARK) == 1, 'sidebarList marker not unique'
    assert html.count(END_MARK) == 1, 'main marker not unique'

    pre, rest = html.split(START_MARK, 1)
    _mid, post = rest.split(END_MARK, 1)

    new_html = pre + START_MARK + '\n' + sidebar_html + '\n\n        </div>\n' + END_MARK + post
    with open(INDEX_PATH, 'w', encoding='utf-8') as f:
        f.write(new_html)

    tasks = defaultdict(int)
    for c in cards:
        t = gm.classify(c)
        tasks[int(t) if t else 0] += 1
    print('sidebar rebuilt:', len(cards), 'cards across tasks',
          dict(sorted(tasks.items())))


if __name__ == '__main__':
    main()
