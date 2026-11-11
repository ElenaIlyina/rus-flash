"""Regressions for Н/НН form distinctions and source preservation."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
spec = importlib.util.spec_from_file_location('n_renderer', ROOT / 'dev/scripts/review_n_explanations.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

def read(path):
    return json.loads((ROOT / path).read_text())

class NReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in read('dev/data/knowledge/n_card_reviews.json')['cards']}

    def test_all_positions_are_reproducible_and_source_linked(self):
        self.assertEqual(len(self.reviews), 71)
        self.assertEqual(sum(len(r['rows']) for r in self.reviews.values()), 257)
        support = read('data/knowledge/card_support.json')['cards']
        for cid, review in self.reviews.items():
            card = read(f'data/card_{cid}.json')
            self.assertTrue(review['rewriteReview']['previousExplanationNotTrusted'])
            self.assertEqual(renderer.render(card, review), card['explanation'])
            self.assertEqual(hashlib.sha256(card['explanation'].encode()).hexdigest(), review['explanationSha256'])
            self.assertTrue(support[cid]['hint'])
            self.assertTrue(support[cid]['ruleSourceRefs'])

    def test_short_participle_does_not_inherit_double_n_from_ova(self):
        self.assertEqual(self.reviews['56D1C0']['rows'][3]['word'], 'нарисованы')
        self.assertEqual(self.reviews['56D1C0']['rows'][3]['nCount'], 1)
        self.assertEqual(self.reviews['636926']['rows'][2]['nCount'], 2)

    def test_compounding_alone_does_not_force_double_n(self):
        self.assertEqual(self.reviews['4905E4']['rows'][0]['nCount'], 1)
        self.assertEqual(self.reviews['049337']['rows'][1]['nCount'], 2)

    def test_short_adjective_is_distinguished_from_short_participle(self):
        self.assertEqual(self.reviews['B0CDE1']['rows'][1]['word'], 'пустынны')
        self.assertEqual(self.reviews['B0CDE1']['rows'][1]['nCount'], 2)
        self.assertEqual(self.reviews['C6AFC3']['rows'][1]['nCount'], 1)
        self.assertEqual(self.reviews['C6AFC3']['rows'][3]['nCount'], 2)

    def test_latin_e_is_normalized_only_with_an_explicit_record(self):
        card = read('data/card_C6AFC3.json')
        self.assertIn('Краш</b><b>e(1)', card['question'])
        review = copy.deepcopy(self.reviews['C6AFC3'])
        self.assertEqual(review['rows'][0]['word'], 'Крашенные')
        del review['rows'][0]['sourceGlyphs']
        with self.assertRaisesRegex(ValueError, 'Word differs'):
            renderer.render(card, review)

    def test_changing_count_cannot_silently_change_a_checked_key(self):
        review = copy.deepcopy(self.reviews['015A7C'])
        review['rows'][3].update(nCount=2, word='учтенно')
        with self.assertRaisesRegex(ValueError, 'historical key'):
            renderer.render(read('data/card_015A7C.json'), review)

    def test_source_passage_is_frozen(self):
        card = read('data/card_015A7C.json')
        card['question'] += ' Изменение.'
        with self.assertRaisesRegex(ValueError, 'Source task changed'):
            renderer.render(card, self.reviews['015A7C'])

if __name__ == '__main__':
    unittest.main()
