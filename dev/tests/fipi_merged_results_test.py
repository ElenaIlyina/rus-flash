"""Audit real returned reports without live network calls."""
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
        for name in ['2026-10-29-first-run','2026-10-29-pending-run','2026-10-29-pending-repeat-run','2026-10-29-retry-run','2026-10-29-final-6E2A0F','2026-10-29-final-8CD68D']:
            p=ROOT / 'dev/data/fipi-results' / name / 'report.json'
            cls.reports.append((json.loads(p.read_text()),hashlib.sha256(p.read_bytes()).hexdigest()))
        with zipfile.ZipFile(ROOT / 'dev/docs/references/fipi-bank-2026-10-29/source.zip') as archive:
            cls.snapshots = {c['number']:c for c in (json.loads(archive.read(name)) for name in archive.namelist()
                             if name.startswith('src/cards/card_') and name.endswith('.json'))}

    def test_merge_and_retry_have_exactly_the_unresolved_cards(self):
        merged=merger.merge(self.reports,self.snapshots)
        self.assertEqual(merged['summary'],{'cards':2140,'acceptedCards':2069,'unresolvedCards':0,
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
        previous=merger.merge(self.reports[:3],self.snapshots)
        self.assertEqual({c['cardId'] for c in manifest['checks']},
                         {c['cardId'] for c in previous['cards'] if c['status']=='no_accepted_answer'})
        self.assertEqual(len(retry['checks']),14)
        rows={c['cardId']:c for c in previous['cards']}
        for check in manifest['checks']:
            self.assertEqual(check['sourceSnapshot'],self.snapshots[check['cardId']])
            rejected={a['wireAnswer'] for a in rows[check['cardId']]['attempts'] if a['status']=='rejected'}
            for answer in check['candidates']:
                self.assertNotIn(answer['wireAnswer'],rejected)
                self.assertEqual(answer['wireAnswer'],checker.wire_answer(check['sourceSnapshot'],answer['answer']))

    def test_final_two_plan_matches_unresolved_cards_and_uses_fresh_candidates(self):
        merged=merger.merge(self.reports[:4],self.snapshots)
        plan=checker.load_plan(ROOT/'dev/data/fipi_final_two_checks.json')
        self.assertEqual(plan['previousReportSha256'],self.reports[3][1])
        unresolved={c['cardId']:c for c in merged['cards'] if c['status']=='no_accepted_answer'}
        self.assertEqual({c['cardId'] for c in plan['checks']},set(unresolved))
        self.assertEqual({c['cardId']:c['candidates'][0]['answer'] for c in plan['checks']},
                         {'6E2A0F':'263133','8CD68D':'2526'})
        for check in plan['checks']:
            self.assertEqual(check['sourceSnapshot'],self.snapshots[check['cardId']])
            rejected={a['wireAnswer'] for a in unresolved[check['cardId']]['attempts']}
            for candidate in check['candidates']:
                self.assertNotIn(candidate['wireAnswer'],rejected)
                self.assertEqual(candidate['wireAnswer'],checker.wire_answer(check['sourceSnapshot'],candidate['answer']))

    def test_final_original_reports_close_both_remaining_cards(self):
        before=merger.merge(self.reports[:4],self.snapshots)
        after=merger.merge(self.reports,self.snapshots)
        self.assertEqual(before['summary']['unresolvedCards'],2)
        rows={c['cardId']:c for c in after['cards']}
        for cid,answer in [('6E2A0F','3133'),('8CD68D','2526')]:
            self.assertEqual(rows[cid]['acceptedWireAnswers'],[answer])
            attempts=[a for a in rows[cid]['attempts'] if a['status']=='accepted']
            self.assertEqual(len(attempts),1)
            self.assertIn(attempts[0]['evidenceReportSha256'],[sha for _,sha in self.reports[-2:]])
        self.assertNotIn('263133',[a['wireAnswer'] for a in rows['6E2A0F']['attempts']])
        self.assertEqual(after['summary']['unresolvedCards'],0)
        self.assertEqual(after['summary']['acceptedCards']+after['summary']['essayCards'],2140)

    def test_repeated_run_does_not_inflate_accepted_card_counts(self):
        previous=merger.merge(self.reports[:2],self.snapshots)
        repeated=merger.merge(self.reports[:3],self.snapshots)
        self.assertEqual(previous['summary'],repeated['summary'])
        before={c['cardId']:c for c in previous['cards']}
        for card in repeated['cards']:
            self.assertEqual(card['acceptedWireAnswers'],before[card['cardId']]['acceptedWireAnswers'])
        self.assertEqual(sum(len(c['attempts']) for c in repeated['cards'])-
                         sum(len(c['attempts']) for c in previous['cards']),691)

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
