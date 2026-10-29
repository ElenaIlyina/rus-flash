#!/usr/bin/env python3
"""Select plain-text entries from already unpacked MOBI7 HTML; preparation only.

Unpack the user MOBI with mobi 0.4.1 first. This script never runs source HTML,
copies event handlers, or includes morphological idx:infl metadata in articles.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata


def extract(raw, selected):
    entries = {}
    for match in re.finditer(r'<idx:entry\b[^>]*>(.*?)</idx:entry>', raw, re.S):
        blob = match[1]
        head = re.search(r'<idx:orth value="([^"]+)"', blob)
        if not head:
            continue
        word = unicodedata.normalize('NFC', html.unescape(head[1])).lower().replace('ё', 'е')
        if word not in selected:
            continue
        blob = re.sub(r'<idx:orth\b.*?</idx:orth>', '', blob, flags=re.S)
        blob = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', blob, flags=re.S | re.I)
        blob = re.sub(r'</div\s*>', '\n', blob, flags=re.I)
        plain = html.unescape(re.sub(r'<[^>]+>', '', blob))
        plain = '\n'.join(' '.join(line.split()) for line in plain.splitlines() if line.strip())
        entries[word] = {'id': 'ozhegov-' + hashlib.sha256(word.encode()).hexdigest()[:12],
                         'dictionaryId': 'ozhegov-shvedova-user-copy', 'headword': word,
                         'text': plain, 'textSha256': hashlib.sha256(plain.encode()).hexdigest()}
    if selected - entries.keys():
        raise ValueError('Missing selected articles: ' + ', '.join(sorted(selected - entries.keys())))
    return list(entries.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('unpacked_html')
    parser.add_argument('article_registry', help='existing read-articles.json, used only for the headword selection')
    parser.add_argument('output')
    args = parser.parse_args()
    selected = {a['headword'] for a in json.loads(Path(args.article_registry).read_text())['entries']}
    entries = extract(Path(args.unpacked_html).read_text(), selected)
    Path(args.output).write_text(json.dumps({'entries': entries}, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
