#!/usr/bin/env python3
"""Verify locally downloaded primary grammar pages against editorial fingerprints.

Save each source URL as wbw-grammar-<last URL segment>.html in --html-dir.
No complete course text is copied into application data.
"""
import argparse
import hashlib
import re
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
from review_grammar_explanations import load_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html-dir', type=Path, required=True)
    args = parser.parse_args()
    sources = load_sources()
    for source in sources.values():
        if source.get('format') == 'pdf':
            path = args.html_dir / source['snapshotName']
            if hashlib.sha256(path.read_bytes()).hexdigest() != source['fileSha256']:
                raise ValueError('Source PDF changed: '+source['id'])
            page = str(source['pdfPage'])
            text = subprocess.check_output(['pdftotext','-f',page,'-l',page,'-layout',str(path),'-']).decode()
            if hashlib.sha256(text.encode()).hexdigest() != source['textSha256'] or source['anchor'] not in re.sub(r'\s+', ' ', text):
                raise ValueError('Source PDF page changed: '+source['id'])
            continue
        slug = source['url'].rstrip('/').rsplit('/', 1)[1]
        raw = (args.html_dir / ('wbw-grammar-'+slug+'.html')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source['htmlSha256']:
            raise ValueError('Downloaded HTML changed: '+source['id'])
        document = BeautifulSoup(raw, 'html.parser', from_encoding=source.get('encoding'))
        article = document.select_one(source['selector'])
        if source.get('questionSelector'):
            question = document.select_one(source['questionSelector'])
            if question is None or hashlib.sha256(question.get_text(' ', strip=True).encode()).hexdigest() != source['questionSha256']:
                raise ValueError('Source question changed: '+source['id'])
        if article is None:
            raise ValueError('Source article selector missing: '+source['id'])
        for tag in article.select('script, style'):
            tag.decompose()
        text = article.get_text(' ', strip=True)
        if hashlib.sha256(text.encode()).hexdigest() != source['textSha256'] or source['anchor'] not in text:
            raise ValueError('Source text or section anchor changed: '+source['id'])
    print(f'Grammar source fingerprints checked: {len(sources)}')


if __name__ == '__main__':
    main()
