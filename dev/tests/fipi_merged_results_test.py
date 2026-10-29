"""Audit two real returned reports without live network calls."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT / 'dev/scripts'))
import check_fipi_answers as checker
import merge_fipi_check_results as merger


class MergedResultsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports = []
        for name in ['2026-10-29-first-run','2026-10-29-pending-run']:
            p=ROOT / 'dev/data/fipi-results' / name / 'report.json'
            cls.reports.append((json.loads(p.read_text()),hashlib.sha256(p.read_bytes()).hexdigest()))
        with zipfile.ZipFile(ROOT / 'dev/docs/references/fipi-bank-2026-10-29/source.zip') as archive:
            cls.snapshots = {c['number']:c for c in (json.loads(archive.read(name)) for name in archive.namelist()
                             if name.startswith('src/cards/card_') and name.endswith('.json'))}

    def test_merge_and_retry_have_exactly_the_unresolved_cards(self):
        merged=merger.merge(self.reports,self.snapshots)
        self.assertEqual(merged['summary'],{'cards':2140,'acceptedCards':2055,'unresolvedCards':14,
                                         'essayCards':71,'withMultipleAcceptedStrings':2})
        self.assertEqual(merged,json.loads((ROOT/'dev/data/fipi-results/merged-ledger.json').read_text()))
        # Use archive snapshots for completeness checks independently of generated local files.
        manifest=checker.load_plan(ROOT/'dev/data/fipi_retry_checks.json')
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            ids=[c['cardId'] for c in manifest['checks']] + ['005141']
            for cid in ids:
                (directory/('card_'+cid+'.json')).write_text(json.dumps(self.snapshots[cid],ensure_ascii=False),encoding='utf-8')
            retry=checker.validate_plan(checker.plan_from_cards(directory,checker.load_plan(checker.DEFAULT_PLAN),retry_only=True))
        self.assertEqual({c['cardId'] for c in manifest['checks']},
                         {c['cardId'] for c in merged['cards'] if c['status']=='no_accepted_answer'})
        self.assertEqual(len(retry['checks']),14)
        rows={c['cardId']:c for c in merged['cards']}
        for check in manifest['checks']:
            self.assertEqual(check['sourceSnapshot'],self.snapshots[check['cardId']])
            rejected={a['wireAnswer'] for a in rows[check['cardId']]['attempts'] if a['status']=='rejected'}
            for answer in check['candidates']:
                self.assertNotIn(answer['wireAnswer'],rejected)
                self.assertEqual(answer['wireAnswer'],checker.wire_answer(check['sourceSnapshot'],answer['answer']))

    def test_chain_tampering_duplicate_rows_or_error_bodies_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'предшествующий'):
            merger.merge(self.reports[1:],self.snapshots)
        reports=copy.deepcopy(self.reports)
        reports[1][0]['results'].append(reports[1][0]['results'][0])
        with self.assertRaisesRegex(ValueError,'Повтор'):
            merger.merge(reports,self.snapshots)
        reports=copy.deepcopy(self.reports)
        attempt=next(a for r in reports[1][0]['results'] for a in r['attempts'] if a['status']=='accepted')
        attempt['httpStatus']=403
        with self.assertRaisesRegex(ValueError,'свидетельство'):
            merger.merge(reports,self.snapshots)


if __name__=='__main__':
    unittest.main()
