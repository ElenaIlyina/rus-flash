"""Protect task-25 text boundaries, answer forms, dictionary evidence and open issues."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import review_lexical_analysis as review


class LexicalAnalysisReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in review.read_registry()['cards']}
        cls.sources = review.load_sources()

    def card(self, cid):
        return json.loads((ROOT / f'data/card_{cid}.json').read_text())

    def test_prepared_content_reproduces_public_explanations(self):
        for cid, entry in self.reviews.items():
            self.assertEqual(review.render(self.card(cid), entry, self.sources), self.card(cid)['explanation'])

    def test_requested_range_including_interior_cannot_be_skipped(self):
        r = copy.deepcopy(self.reviews['01D3AC'])
        self.assertEqual(review.target_numbers(self.card(r['id'])), set(range(18, 26)))
        self.assertEqual(review.target_numbers(self.card('2ABC16')), {31})
        r['evidence'] = [e for e in r['evidence'] if e['sentence'] != 21]
        with self.assertRaises(ValueError): review.validate(self.card(r['id']), r, self.sources)

    def test_comma_list_reads_each_sentence_without_inventing_a_range(self):
        self.assertEqual(review.target_numbers(self.card('46ECED')), {22, 23})
        self.assertEqual(review.target_numbers({'question':'Из предложений 22, 24 выпишите синонимы.'}), {22, 24})
        r = copy.deepcopy(self.reviews['46ECED'])
        r['evidence'] = [e for e in r['evidence'] if e['sentence'] != 23]
        with self.assertRaises(ValueError): review.validate(self.card(r['id']), r, self.sources)

    def test_quotes_forms_and_source_evidence_cannot_be_substituted(self):
        r = self.reviews['13D9BA']
        for change in [lambda x:x.update(answer='взыскательные'), lambda x:x['evidence'][0].update(quote='выдуманная цитата'), lambda x:x.update(lexicalEvidence=[]), lambda x:x['lexicalEvidence'][0].update(textSha256='bad'), lambda x:x['rewriteReview'].update(oldExplanationsUsedAsEvidence=True)]:
            broken = copy.deepcopy(r); change(broken)
            with self.assertRaises(ValueError): review.validate(self.card(r['id']), broken, self.sources)

    def test_even_matching_keys_cannot_invent_a_word_absent_from_range(self):
        r = copy.deepcopy(self.reviews['13D9BA']); c = self.card(r['id'])
        c['answer'] = c['answer_verify'] = r['answer'] = 'несуществующее'
        r['sourceContentSha256'] = review.frozen(c)
        with self.assertRaises(ValueError): review.validate(c, r, self.sources)

    def test_open_alternative_answers_remain_visible_without_expanding_key(self):
        for cid in ['01D3AC', '05AC9F', '1DA0CC']:
            r = self.reviews[cid]
            self.assertIn(r['sourceReviewNote'], review.render(self.card(cid), r, self.sources))
            broken = copy.deepcopy(r); broken['sourceReviewPending'] = False
            with self.assertRaises(ValueError): review.validate(self.card(cid), broken, self.sources)

    def test_clickable_refs_match_verified_catalog(self):
        for entry in self.reviews.values():
            refs = review.public_refs(entry, self.sources)
            self.assertTrue(refs)
            self.assertTrue(all(ref['part'] == 1 and (ref['url'].startswith('https://gramota.ru/') or ref['url'] in {'https://lib.ru/DIC/OZHEGOW/ozhegow_a_d.txt', 'https://lib.ru/DIC/OZHEGOW/ozhegow_e_l.txt'}) for ref in refs))
