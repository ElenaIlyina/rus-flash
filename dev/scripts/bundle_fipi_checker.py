#!/usr/bin/env python3
"""Refresh the standalone checker's embedded previously verified answer set."""
import json
from pathlib import Path
import pprint

ROOT = Path(__file__).resolve().parents[2]
path = ROOT / 'dev/scripts/check_fipi_answers.py'
cards = [json.loads(p.read_text()) for p in sorted((ROOT / 'data').glob('card_*.json'))]
answers = {c['guid'].lower(): (c['number'], c['answer']) for c in cards
           if c.get('answer', '').strip() and c.get('answer_verify', '').strip()}
source = path.read_text()
begin = source.index('# BEGIN EMBEDDED ANSWERS')
end = source.index('# END EMBEDDED ANSWERS', begin)
source = source[:begin] + '# BEGIN EMBEDDED ANSWERS — refreshed by bundle_fipi_checker.py\n' + \
    'EMBEDDED_ANSWERS = ' + pprint.pformat(answers, width=110, sort_dicts=True) + '\n' + source[end:]
path.write_text(source)
print(f'Embedded {len(answers)} existing answers; no application cards changed')
