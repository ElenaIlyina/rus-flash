"""Style criteria can be linked without accepting or modifying existing explanations."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
from review_grammar_explanations import load_sources
from review_style_sources import validate


def read(path):
    return json.loads((ROOT / path).read_text())


class StyleSourceReviewTest(unittest.TestCase):
    def test_published_links_match_context_review(self):
        sources = load_sources()
        support = read('data/knowledge/card_support.json')['cards']
        for review in read('dev/data/knowledge/style_source_reviews.json')['cards']:
            card = read('data/card_'+review['id']+'.json')
            self.assertEqual(validate(card, review, sources), support[review['id']]['styleSourceRefs'])
            self.assertTrue(review['doesNotValidateExistingExplanation'])

    def test_every_task3_card_has_one_complete_source_mapping(self):
        from exam_2027 import mapping
        reviews = read('dev/data/knowledge/style_source_reviews.json')['cards']
        expected = {c['number'] for path in (ROOT / 'data').glob('card_*.json')
                    if mapping(c := json.loads(path.read_text()))['task'] == 3}
        self.assertEqual(len(reviews), len(expected))
        self.assertEqual({r['id'] for r in reviews}, expected)
        for review in reviews:
            self.assertEqual(review['rewriteReview']['oldExplanationsUsedAsEvidence'], False)

    def test_changed_variant_is_not_given_the_old_source_mapping(self):
        review = read('dev/data/knowledge/style_source_reviews.json')['cards'][0]
        card = read('data/card_'+review['id']+'.json')
        card['variants'][0] += ' Изменение.'
        with self.assertRaises(ValueError):
            validate(card, review, load_sources())

    def test_source_only_pass_cannot_be_presented_as_explanation_acceptance(self):
        review = copy.deepcopy(read('dev/data/knowledge/style_source_reviews.json')['cards'][0])
        card = read('data/card_'+review['id']+'.json')
        review['doesNotValidateExistingExplanation'] = False
        with self.assertRaises(ValueError):
            validate(card, review, load_sources())


if __name__ == '__main__':
    unittest.main()
