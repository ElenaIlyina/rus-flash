#!/usr/bin/env python3
"""Reproduce the supplementary stress audit from the two pinned public PDFs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'dev/docs/content-audit/stress-dictionary-crosscheck.json'

def verify(paths, include_roots=False):
    report = json.loads(REPORT.read_text())
    sources = {source['id']: source for source in report['sources']}
    pages = {}
    for source_id, path in paths.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sources[source_id]['sha256']:
            raise ValueError(f'{source_id}: PDF checksum differs from the reviewed copy')
    forms = list(report['forms'])
    if include_roots:
        root_report = json.loads((ROOT / 'dev/docs/content-audit/root-dictionary-evidence.json').read_text())
        forms += [{'form': ref['form'], 'evidence': [dict(ref, printedToken=ref['form'])]}
                  for ref in root_report['stressForms']]
    checked = 0
    for form in forms:
        for evidence in form['evidence']:
            source_id = evidence['sourceId']
            key = (source_id, evidence['pdfPage'])
            if key not in pages:
                page = str(key[1])
                text = subprocess.check_output(['pdftotext', '-layout', '-f', page, '-l', page,
                                                str(paths[source_id]), '-'], text=True)
                # pdftotext emits one final page separator, also present in whole-file extraction.
                pages[key] = text.removesuffix('\f')
            text = pages[key]
            if hashlib.sha256(text.encode()).hexdigest() != evidence['pageTextSha256']:
                raise ValueError(f'{form["form"]}: page extraction checksum differs')
            if evidence['printedToken'].casefold() not in text.casefold():
                raise ValueError(f'{form["form"]}: printed token absent from cited page')
            checked += 1
    return checked

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--orthoepic', required=True, type=Path)
    parser.add_argument('--orthographic', required=True, type=Path)
    parser.add_argument('--roots', action='store_true', help='Also verify every stressed form in the root review')
    args = parser.parse_args()
    count = verify({'gramota-state-orthoepic-pdf': args.orthoepic,
                    'gramota-state-orthographic-pdf': args.orthographic}, include_roots=args.roots)
    print(f'Verified {count} page references; no card files changed.')

if __name__ == '__main__':
    main()
