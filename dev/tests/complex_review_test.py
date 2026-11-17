"""Task-20 scope, frozen keys, nested clauses and unresolved interpretations."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dev/scripts'))
import review_complex_explanations as review
from handbook_fb2 import read_handbook


class ComplexReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in review.read_registry()['cards']}
        _, ps = read_handbook(ROOT/'data/knowledge/sources/lopatin-2007.fb2.zip')
        cls.ps = {p['id']:p for p in ps}

    def card(self, cid):
        return json.loads((ROOT/f'data/card_{cid}.json').read_text())

    def test_all_88_cards_reproduce_and_both_keys_stay_exact(self):
        self.assertEqual(len(self.reviews),88)
        self.assertEqual(sum(len(r['rows']) for r in self.reviews.values()),364)
        for cid,r in self.reviews.items():
            self.assertEqual(review.render(self.card(cid),r,self.ps),self.card(cid)['explanation'])
            self.assertEqual(''.join(str(v['number']) for v in r['rows'] if v['comma']),self.card(cid)['answer_verify'])

    def test_one_word_changes_stacked_conjunction_decision(self):
        simple = self.reviews['407ACB']
        double = self.reviews['FF27D3']
        self.assertTrue(simple['rows'][1]['comma'])
        self.assertFalse(double['rows'][1]['comma'])
        self.assertIn('то он молча',review.validate(self.card('FF27D3'),double,self.ps))

    def test_nested_definition_closes_before_homogeneous_predicate(self):
        r=self.reviews['C5985D']
        text=review.validate(self.card(r['id']),r,self.ps)
        self.assertIn('где прежде сидел отец, и ест',text)
        self.assertIn('закрывает придаточное',r['rows'][4]['reason'])

    def test_main_homogeneous_predicates_and_return_after_subclause(self):
        for cid in ['957535','98C807','A2D7E9','B710C5','C7CE1D','E85B44']:
            r=self.reviews[cid]
            self.assertFalse(r['rows'][1 if cid=='C7CE1D' else 0]['comma'])
        self.assertTrue(self.reviews['7D08DE']['rows'][2]['comma'])
        self.assertIn('закрывает придаточное',self.reviews['7D08DE']['rows'][2]['reason'])

    def test_question_key_and_evidence_mutations_are_rejected(self):
        r=self.reviews['05C201']
        for field in ['question','answer','answer_verify']:
            c=self.card(r['id']);c[field]+='x'
            with self.assertRaises(ValueError): review.validate(c,r,self.ps)
        for mutate in [lambda x:x['rows'].pop(),lambda x:x['paragraphEvidence'][0].update(textSha256='wrong'),lambda x:x['rewriteReview'].update(oldExplanationsUsedAsEvidence=True)]:
            broken=copy.deepcopy(r);mutate(broken)
            with self.assertRaises(ValueError):review.validate(self.card(r['id']),broken,self.ps)

    def test_uncertainty_cannot_silently_be_published_as_settled(self):
        pending={cid for cid,r in self.reviews.items() if r.get('sourceReviewPending')}
        self.assertEqual(pending,{'503B73','A0805E'})
        for cid in pending:
            r=self.reviews[cid]
            self.assertIn('Требует уточнения',review.render(self.card(cid),r,self.ps))
            broken=copy.deepcopy(r);broken['sourceReviewPending']=False
            with self.assertRaises(ValueError):review.validate(self.card(cid),broken,self.ps)
