"""Task-21 classifies each source sentence, not the visible glyph alone."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dev/scripts'))
import review_punctuation_analysis as review
from handbook_fb2 import read_handbook


class PunctuationAnalysisTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews={r['id']:r for r in review.read_registry()['cards']}
        _,ps=read_handbook(ROOT/'data/knowledge/sources/lopatin-2007.fb2.zip')
        cls.ps={p['id']:p for p in ps}

    def card(self,cid):
        return json.loads((ROOT/f'data/card_{cid}.json').read_text())

    def test_all_58_cards_cover_every_sentence_and_reproduce(self):
        self.assertEqual(len(self.reviews),58)
        for cid,r in self.reviews.items():
            self.assertEqual(review.render(self.card(cid),r,self.ps),self.card(cid)['explanation'])
            self.assertEqual(len(r['rows']),len(review.sentences(self.card(cid))))

    def test_same_text_with_changed_last_sentence_changes_selection(self):
        self.assertTrue(self.reviews['2F4DC7']['rows'][8]['matchesCommonRule'])
        self.assertFalse(self.reviews['F90A33']['rows'][8]['matchesCommonRule'])
        self.assertIn('которые',review.sentences(self.card('2F4DC7'))[8])
        self.assertNotIn('которые',review.sentences(self.card('F90A33'))[8])

    def test_apposition_is_not_predicate_or_missing_verb(self):
        r=self.reviews['957CC8']
        self.assertEqual([v['number'] for v in r['rows'] if v['matchesCommonRule']],[1,2])
        self.assertIn('пропущено',r['rows'][3]['reason'])
        self.assertIn('прямую речь',r['rows'][4]['reason'])

    def test_different_comma_functions_within_selected_sentence(self):
        r=self.reviews['19F797']['rows'][2]
        self.assertTrue(r['matchesCommonRule'])
        self.assertEqual(len(r['sourceIds']),3)
        self.assertIn('приветствуя',r['reason'].lower())

    def test_subtype_of_same_function_is_not_false_participle(self):
        r=self.reviews['E718F6']
        self.assertIn('определений',r['commonRule'])
        self.assertIn('два согласованных определения',r['rows'][4]['reason'])
        self.assertIn('lopatin-2007-punctuation-48',r['rows'][4]['sourceIds'])

    def test_key_text_evidence_scope_and_pending_cannot_be_forged(self):
        r=self.reviews['04262D']
        for change in [lambda x:x['rows'].pop(),lambda x:x['rows'][0].update(sentenceSha256='bad'),lambda x:x['rows'][0].update(matchesCommonRule=True),lambda x:x['rewriteReview'].update(oldExplanationsUsedAsEvidence=True)]:
            broken=copy.deepcopy(r);change(broken)
            with self.assertRaises(ValueError):review.validate(self.card(r['id']),broken,self.ps)
        pending=copy.deepcopy(self.reviews['1E7690']);pending['sourceReviewPending']=False
        with self.assertRaises(ValueError):review.validate(self.card(pending['id']),pending,self.ps)
