"""Task-22 explanations preserve matching order, quotes, source evidence and doubts."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import review_rhetoric_explanations as review


class RhetoricReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in review.read_registry()['cards']}
        cls.sources = review.load_sources()

    def card(self, cid):
        return json.loads((ROOT / f'data/card_{cid}.json').read_text())

    def test_all_71_cards_reproduce_with_both_original_formats(self):
        self.assertEqual(len(self.reviews), 71)
        self.assertEqual(sum(r['format'] == 'modern_matching' for r in self.reviews.values()), 13)
        self.assertEqual(sum(len(r['rows']) for r in self.reviews.values()), 297)
        for cid, r in self.reviews.items():
            self.assertEqual(review.render(self.card(cid), r, self.sources), self.card(cid)['explanation'])

    def test_wrong_order_term_quote_evidence_and_provenance_rejected(self):
        r = self.reviews['1E12FC']
        for change in [lambda x:x['rows'].reverse(), lambda x:x['rows'].pop(), lambda x:x['rows'][0].update(term='другой термин'), lambda x:x['rows'][0].update(quote='выдуманная цитата'), lambda x:x['rows'][0]['sourceEvidence'][0].update(textSha256='bad'), lambda x:x['rewriteReview'].update(oldExplanationsUsedAsEvidence=True)]:
            broken = copy.deepcopy(r); change(broken)
            with self.assertRaises(ValueError): review.validate(self.card(r['id']), broken, self.sources)
        c = self.card(r['id']); c['answer'] = c['answer'][::-1]
        with self.assertRaises(ValueError): review.validate(c, r, self.sources)

    def test_historical_quote_must_be_present_in_source(self):
        r = copy.deepcopy(self.reviews['FAC079']); r['rows'][0]['quote'] = 'выдуманная цитата'
        with self.assertRaises(ValueError): review.validate(self.card(r['id']), r, self.sources)

    def test_doubts_are_not_silently_accepted_as_proof(self):
        pending = {cid for cid, r in self.reviews.items() if r.get('sourceReviewPending')}
        self.assertEqual(pending, {'00EA20', '66CDCF', '6A4DD9'})
        for cid in pending:
            r = copy.deepcopy(self.reviews[cid]); r['sourceReviewPending'] = False
            with self.assertRaises(ValueError): review.validate(self.card(cid), r, self.sources)
        self.assertIn('шкалы', self.reviews['66CDCF']['hint'])
        self.assertIn('разговорно-сниженное', self.reviews['6A4DD9']['rows'][2]['reason'])

    def test_public_sources_and_local_handbook_are_separate(self):
        for r in self.reviews.values():
            self.assertTrue(review.public_refs(r, self.sources) or review.local_refs(r, self.sources))
            self.assertTrue(all(ref['url'].startswith('https:') for ref in review.public_refs(r, self.sources)))
            self.assertTrue(all(ref['sourceId'].startswith('lopatin-2007-punctuation-') for ref in review.local_refs(r, self.sources)))
        self.assertIn('Кожиной', review.render(self.card('1E12FC'), self.reviews['1E12FC'], self.sources))

    def test_general_term_does_not_erase_more_specific_form(self):
        self.assertIn('анафора', self.reviews['FE4686']['rows'][3]['reason'])
        self.assertIn('1-го лица', self.reviews['FAC079']['rows'][3]['reason'])
        self.assertIn('развёрнутая метафора', self.reviews['F7684F']['rows'][0]['reason'])
