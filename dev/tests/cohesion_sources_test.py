"""Context evidence stays tied to original passages, keys, and all listed options."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
from review_cohesion_sources import validate
from review_grammar_explanations import load_sources

class CohesionSourcesTest(unittest.TestCase):
    def setUp(self):
        self.sources = load_sources()
        self.reviews = [r for r in json.loads((ROOT / 'dev/data/knowledge/ege_1_6_card_reviews.json').read_text())['cards'] if r['task'] == 1]

    def card(self, review):
        return json.loads((ROOT / 'data' / ('card_' + review['id'] + '.json')).read_text())

    def test_all_contexts_and_options(self):
        self.assertEqual(len(self.reviews), 77)
        self.assertEqual(sum(len(r['contextSourceReview'].get('choiceAnalysis', [])) for r in self.reviews), 45)
        for r in self.reviews:
            self.assertTrue(validate(self.card(r), r, self.sources))

    def test_changed_passage_or_answer_rejected(self):
        r = self.reviews[0]
        for field in ('text', 'answer'):
            c = self.card(r); c[field] += 'x'
            with self.assertRaises(ValueError): validate(c, r, self.sources)

    def test_unfounded_acceptance_or_stale_source_rejected(self):
        for key in ('answerUniquenessEstablished', 'oldExplanationsUsedAsEvidence', 'independentTeacherAcceptance'):
            r = copy.deepcopy(self.reviews[0]); r['contextSourceReview'][key] = True
            with self.assertRaises(ValueError): validate(self.card(r), r, self.sources)
        r = copy.deepcopy(self.reviews[0]); r['contextSourceReview']['grammarEvidence'][0]['textSha256'] = '0' * 64
        with self.assertRaises(ValueError): validate(self.card(r), r, self.sources)

    def test_missing_option_rejected(self):
        r = copy.deepcopy(next(r for r in self.reviews if 'choiceAnalysis' in r['contextSourceReview']))
        r['contextSourceReview']['choiceAnalysis'].pop()
        with self.assertRaises(ValueError): validate(self.card(r), r, self.sources)

    def test_specific_preposition_reference(self):
        r = next(r for r in self.reviews if r['id'] == '8C38AE')
        self.assertIn('https://artefact.lib.ru/languages/rus_ebooks_rg_1645-1668.shtml#p1658', [s['url'] for s in validate(self.card(r), r, self.sources)])
