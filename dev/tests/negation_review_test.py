"""Regression checks for context-dependent НЕ/НИ and historical word-answer tasks."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
spec = importlib.util.spec_from_file_location('negation_renderer', ROOT / 'dev/scripts/review_negation_explanations.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

def read(path):
    return json.loads((ROOT / path).read_text())

class NegationReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in read('dev/data/knowledge/negation_card_reviews.json')['cards']}

    def test_every_option_has_reproducible_context_review(self):
        self.assertEqual(len(self.reviews), 70)
        self.assertEqual(sum(len(r['rows']) for r in self.reviews.values()), 350)
        word_answers = 0
        support = read('data/knowledge/card_support.json')['cards']
        for cid, review in self.reviews.items():
            card = read(f'data/card_{cid}.json')
            self.assertTrue(review['rewriteReview']['previousExplanationNotTrusted'])
            self.assertEqual(renderer.render(card, review), card['explanation'])
            self.assertEqual(hashlib.sha256(card['explanation'].encode()).hexdigest(), review['explanationSha256'])
            self.assertEqual(len(review['rows']), len(card['variants']))
            self.assertTrue(support[cid]['hint'])
            self.assertTrue(support[cid]['ruleSourceRefs'])
            word_answers += 'выпишите это слово' in card['question'].lower()
        self.assertEqual(word_answers, 51)

    def test_despite_and_visual_action_have_different_spellings(self):
        self.assertEqual(self.reviews['58F6B3']['rows'][0]['spelling'], 'solid')
        self.assertEqual(self.reviews['16D335']['rows'][3]['spelling'], 'separate')
        for cid in ['58F6B3', '16D335']:
            renderer.render(read(f'data/card_{cid}.json'), self.reviews[cid])

    def test_ni_count_phrase_and_negative_pronoun_are_not_confused(self):
        self.assertEqual(self.reviews['58F6B3']['rows'][1]['spelling'], 'separate')
        self.assertEqual(self.reviews['57DAE6']['rows'][0]['spelling'], 'solid')
        self.assertEqual(self.reviews['E7204A']['rows'][4]['spelling'], 'solid')

    def test_context_cue_must_exist_in_the_same_source_option(self):
        review = copy.deepcopy(self.reviews['12D177'])
        review['rows'][1]['contextCue'] = 'придуманное зависимое слово'
        with self.assertRaisesRegex(ValueError, 'Contextual evidence'):
            renderer.render(read('data/card_12D177.json'), review)

    def test_changing_a_spelling_decision_cannot_silently_change_the_key(self):
        review = copy.deepcopy(self.reviews['16D335'])
        review['rows'][1]['spelling'] = 'separate'
        with self.assertRaisesRegex(ValueError, 'historical key'):
            renderer.render(read('data/card_16D335.json'), review)

    def test_source_particle_and_word_must_be_preserved(self):
        review = copy.deepcopy(self.reviews['57DAE6'])
        review['rows'][0]['particle'] = 'не'
        with self.assertRaisesRegex(ValueError, 'source option'):
            renderer.render(read('data/card_57DAE6.json'), review)

if __name__ == '__main__':
    unittest.main()
