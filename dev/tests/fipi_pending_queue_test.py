"""Returned evidence must exclude accepted cards and bind pending answers to raw snapshots."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT / 'dev/scripts'))
import check_fipi_answers as checker
import prepare_pending_fipi_checks as prep


class PendingQueueTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report_path = ROOT / 'dev/data/fipi-results/2026-10-29-first-run/report.json'
        cls.report = json.loads(cls.report_path.read_text())
        cls.report_hash = hashlib.sha256(cls.report_path.read_bytes()).hexdigest()
        with zipfile.ZipFile(ROOT / 'dev/docs/references/fipi-bank-2026-10-29/source.zip') as archive:
            cls.raw = {c['number']:c for c in (json.loads(archive.read(name)) for name in archive.namelist()
                       if name.startswith('src/cards/card_') and name.endswith('.json'))}
        cls.plans = [checker.load_plan(ROOT / 'dev/data' / name)
                     for name in ['fipi_new_hypotheses.json','fipi_remaining_hypotheses.json']]

    def test_complete_reconciliation_and_encoding(self):
        plan, ledger = prep.prepare(self.report,self.raw,self.plans,self.report_hash)
        self.assertEqual(ledger['summary'],{'cards':2140,'acceptedCards':1388,'pendingCards':681,'essayCards':71})
        stored = checker.load_plan(ROOT / 'dev/data/fipi_pending_checks.json')
        self.assertEqual(plan,stored)
        accepted = {c['guid'].lower() for c in ledger['accepted']}
        self.assertTrue(accepted.isdisjoint(checker.EMBEDDED_PENDING_HYPOTHESES))
        self.assertEqual(len(checker.EMBEDDED_PENDING_HYPOTHESES),681)
        self.assertEqual({c['cardId'] for c in plan['checks']} & set(ledger['essayIds']),set())
        for check in plan['checks']:
            for answer in check['candidates']:
                self.assertEqual(answer['wireAnswer'],checker.wire_answer(check['sourceSnapshot'],answer['answer']))
        recheck = next(c for c in plan['checks'] if c['cardId']=='D30EAB')
        self.assertEqual([c['answer'] for c in recheck['candidates']],['25'])
        self.assertEqual(recheck['candidates'][0]['wireAnswer'],'01001')
        for check in self.plans[1]['checks']:
            if check.get('contextSha256'):
                canonical = json.loads((ROOT / check['contextSource']).read_text())
                self.assertEqual(check['contextSha256'],hashlib.sha256(canonical['text'].encode()).hexdigest())

    def test_inconsistent_server_response_is_not_evidence(self):
        report = copy.deepcopy(self.report)
        row = next(c for c in report['results'] if c['attempts'])
        row['attempts'][0]['httpStatus'] = 403
        with self.assertRaisesRegex(ValueError,'свидетельство'):
            prep.prepare(report,self.raw,self.plans,self.report_hash)
        row['attempts'][0]['httpStatus'] = 200
        row['attempts'][0]['response'] = '2'
        with self.assertRaisesRegex(ValueError,'свидетельство'):
            prep.prepare(report,self.raw,self.plans,self.report_hash)

    def test_duplicate_or_changed_source_cannot_be_merged(self):
        report = copy.deepcopy(self.report)
        report['results'].append(report['results'][0])
        with self.assertRaisesRegex(ValueError,'Повтор'):
            prep.prepare(report,self.raw,self.plans,self.report_hash)
        report = copy.deepcopy(self.report)
        report['results'][0]['sourceContentSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError,'Исходник'):
            prep.prepare(report,self.raw,self.plans,self.report_hash)


if __name__=='__main__':
    unittest.main()
