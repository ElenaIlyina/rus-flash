#!/usr/bin/env python3
"""Extract the reviewed pages of user-supplied books; originals remain unchanged."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from pypdf import PdfReader, PdfWriter
ROOT = Path(__file__).resolve().parents[2]


def payloads():
    sources = [
        ('denisov-morkovkin-1983', ROOT / 'dev/docs/references/denisov-morkovkin-1983/source.pdf', [2, 3, 36, 37, 168, 409, 480, 481, 485], [None, None, 35, 36, 167, 408, 479, 480, 484], 'П. Н. Денисов, В. В. Морковкин (ред.). Словарь сочетаемости слов русского языка. 2-е изд. М.: Русский язык, 1983'),
        ('rozental-stylistics-2001', next((ROOT.parent / 'materials_new').glob('*Практическая*стилистика*.pdf')), [2, 3, 63, 64, 65], [None, None, 62, 63, 64], 'Д. Э. Розенталь. Практическая стилистика. М.: ОНИКС 21 век; Мир и образование, 2001. ISBN 5-329-00322-9'),
    ]
    manifest, files = [], {}
    for sid, original, pages, printed, title in sources:
        raw = original.read_bytes()
        reader, writer = PdfReader(io.BytesIO(raw)), PdfWriter()
        for page in pages:
            writer.add_page(reader.pages[page - 1])
        writer.add_metadata({'/Title': title + ' — выбранные страницы', '/Subject': 'PDF-страницы оригинала: ' + ', '.join(map(str, pages))})
        output = io.BytesIO(); writer.write(output); data = output.getvalue()
        name = f'data/knowledge/sources/lexical/{sid}.pdf'
        files[name] = data
        manifest.append({'id': sid, 'title': title, 'file': name, 'sha256': hashlib.sha256(data).hexdigest(), 'originalFile': str(original.relative_to(ROOT.parent)), 'originalSha256': hashlib.sha256(raw).hexdigest(), 'originalPdfPages': pages, 'printedPages': printed, 'pdfPages': len(pages), 'readMethod': 'visual_page_read', 'note': 'Выбранные страницы пользовательской копии. OCR использовался только для поиска. Издание 1983 года не отождествляется с изданием 2002 года.' if 'denisov' in sid else 'Выбранные страницы пользовательской копии; выходные данные и §7 прочитаны по скану.'})
    return manifest, files


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--check', action='store_true'); args = parser.parse_args()
    sources, files = payloads()
    manifest = ROOT / 'dev/data/knowledge/lexical_pdf_sources.json'
    for name, raw in files.items():
        path = ROOT / name
        if args.check:
            if not path.exists() or path.read_bytes() != raw: raise ValueError('Stale lexical excerpt: ' + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    value = {'schemaVersion': 1, 'sources': sources}
    if args.check:
        if json.loads(manifest.read_text()) != value: raise ValueError('Stale lexical excerpt manifest')
    else: manifest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print('Lexical book excerpts: 2; original pages: 14; originals untouched')


if __name__ == '__main__': main()
