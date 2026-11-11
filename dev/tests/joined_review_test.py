"""Regressions for context-sensitive joined and hyphenated spelling reviews."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
spec = importlib.util.spec_from_file_location('joined_renderer', ROOT / 'dev/scripts/review_joined_explanations.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

def read(path):
    return json.loads((ROOT / path).read_text())

class JoinedReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in read('dev/data/knowledge/joined_card_reviews.json')['cards']}

    def test_every_marked_unit_has_reproducible_context_review(self):
        self.assertEqual(len(self.reviews), 70)
        self.assertEqual(sum(len(row['items']) for r in self.reviews.values() for row in r['rows']), 700)
        word_answers = 0
        support = read('data/knowledge/card_support.json')['cards']
        for cid, review in self.reviews.items():
            card = read(f'data/card_{cid}.json')
            self.assertTrue(review['rewriteReview']['previousExplanationNotTrusted'])
            self.assertEqual(renderer.render(card, review), card['explanation'])
            self.assertEqual(hashlib.sha256(card['explanation'].encode()).hexdigest(), review['explanationSha256'])
            self.assertTrue(support[cid]['hint'])
            word_answers += 'выпишите эти два слова' in card['question'].lower()
        self.assertEqual(word_answers, 51)

    def test_whole_conjunction_and_its_first_word_are_different_marked_units(self):
        whole = self.reviews['08F8BC']['rows'][1]['items'][1]
        first = self.reviews['13C248']['rows'][2]['items'][0]
        self.assertEqual((whole['completed'], whole['spelling']), ('потому что', 'separate'))
        self.assertEqual((first['completed'], first['spelling']), ('потому', 'solid'))

    def test_bank_account_is_not_the_about_preposition(self):
        bank = self.reviews['0B429D']['rows'][3]['items'][1]
        about = self.reviews['3573FE']['rows'][0]['items'][1]
        self.assertEqual(bank['completed'], 'на счёт')
        self.assertEqual(about['completed'], 'насчёт')

    def test_same_parts_can_have_different_contextual_spellings(self):
        free = self.reviews['7C0BEF']['rows'][1]['items'][0]
        cause = self.reviews['07AB3A']['rows'][0]['items'][0]
        self.assertEqual(free['completed'], 'по этому')
        self.assertEqual(cause['completed'], 'поэтому')
        self.assertEqual(free['sourceParts'], cause['sourceParts'])
        self.assertEqual(self.reviews['E48573']['rows'][2]['items'][0]['completed'], 'по чему')

    def test_semantic_uncertainty_must_not_change_answer_selection(self):
        review = copy.deepcopy(self.reviews['3573FE'])
        renderer.render(read('data/card_3573FE.json'), review)
        first = review['rows'][1]['items'][0]
        first.update(spelling='separate', completed='в виду')
        with self.assertRaisesRegex(ValueError, 'Unresolved semantic'):
            renderer.render(read('data/card_3573FE.json'), review)

    def test_source_typo_requires_explicit_editorial_normalization(self):
        card = read('data/card_63227E.json')
        self.assertIn('(ПО) ОСЕНЕМУ', card['variants'][3])
        review = copy.deepcopy(self.reviews['63227E'])
        self.assertEqual(review['rows'][3]['items'][1]['completed'], 'по-осеннему')
        del review['rows'][3]['items'][1]['sourceCorrections']
        with self.assertRaisesRegex(ValueError, 'Completed form'):
            renderer.render(card, review)

    def test_three_source_parts_are_not_reduced_to_two(self):
        whole = self.reviews['15CE24']['rows'][4]['items'][1]
        separate = self.reviews['DFF048']['rows'][0]['items'][1]
        self.assertEqual(whole['sourceParts'], ['в','пол','силы'])
        self.assertEqual(whole['completed'], 'вполсилы')
        self.assertEqual(separate['sourceParts'], ['кое','с','кем'])
        self.assertEqual(separate['completed'], 'кое с кем')

if __name__ == '__main__':
    unittest.main()
