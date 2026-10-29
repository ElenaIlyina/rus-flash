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
plan = json.loads((ROOT / 'dev/data/fipi_retry_checks.json').read_text())
proposals = {c['guid'].lower(): {k:c[k] for k in
             ['cardId','sourceContentSha256','candidates','hypothesisBasis']} for c in plan['checks']}
begin = source.index('# BEGIN RETRY HYPOTHESES')
end = source.index('# END RETRY HYPOTHESES', begin)
source = source[:begin] + '# BEGIN RETRY HYPOTHESES — refreshed by bundle_fipi_checker.py\n' + \
    'RETRY_REPORT_SHA256 = ' + repr(plan['previousReportSha256']) + '\n' + \
    'EMBEDDED_RETRY_HYPOTHESES = json.loads(' + repr(json.dumps(proposals,ensure_ascii=False,separators=(',',':'))) + ')\n' + source[end:]
begin = source.index('# BEGIN EMBEDDED ANSWERS')
end = source.index('# END EMBEDDED ANSWERS', begin)
source = source[:begin] + '# BEGIN EMBEDDED ANSWERS — refreshed by bundle_fipi_checker.py\n' + \
    'EMBEDDED_ANSWERS = ' + pprint.pformat(answers, width=110, sort_dicts=True) + '\n' + source[end:]
path.write_text(source)
plan = json.loads((ROOT / 'dev/data/fipi_pending_checks.json').read_text())
proposals = {c['guid'].lower(): {k:c[k] for k in
             ['cardId','sourceContentSha256','candidates','hypothesisBasis']} for c in plan['checks']}
begin = source.index('# BEGIN PENDING HYPOTHESES')
end = source.index('# END PENDING HYPOTHESES', begin)
source = source[:begin] + '# BEGIN PENDING HYPOTHESES — refreshed by bundle_fipi_checker.py\n' + \
    'PENDING_REPORT_SHA256 = ' + repr(plan['previousReportSha256']) + '\n' + \
    'EMBEDDED_PENDING_HYPOTHESES = json.loads(' + repr(json.dumps(proposals,ensure_ascii=False,separators=(',',':'))) + ')\n' + source[end:]
path.write_text(source)
plan = json.loads((ROOT / 'dev/data/fipi_new_hypotheses.json').read_text())
proposals = {c['guid'].lower(): {k:c[k] for k in
             ['cardId','sourceContentSha256','candidates','hypothesisBasis']} for c in plan['checks']}
begin = source.index('# BEGIN NEW HYPOTHESES')
end = source.index('# END NEW HYPOTHESES', begin)
source = source[:begin] + '# BEGIN NEW HYPOTHESES — refreshed by bundle_fipi_checker.py\n' + \
    'EMBEDDED_NEW_HYPOTHESES = ' + pprint.pformat(proposals, width=110, sort_dicts=True) + '\n' + source[end:]
path.write_text(source)
print(f'Embedded {len(answers)} existing answers; no application cards changed')
plan = json.loads((ROOT / 'dev/data/fipi_answer_variants.json').read_text())
proposals = {c['guid'].lower(): {k:c[k] for k in
             ['cardId','sourceContentSha256','candidates','hypothesisBasis']} for c in plan['checks']}
begin = source.index('# BEGIN VARIANT HYPOTHESES')
end = source.index('# END VARIANT HYPOTHESES', begin)
source = source[:begin] + '# BEGIN VARIANT HYPOTHESES — refreshed by bundle_fipi_checker.py\n' + \
    'EMBEDDED_VARIANT_HYPOTHESES = ' + pprint.pformat(proposals, width=110, sort_dicts=True) + '\n' + source[end:]
path.write_text(source)
