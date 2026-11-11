"""Lexical evidence cannot silently change keys, source pages or unresolved status."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
from review_lexical_sources import load_books, validate
from review_grammar_explanations import load_sources


class LexicalSourcesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources, cls.books = load_sources(), load_books()
        cls.reviews = {r['id']: r for r in json.loads((ROOT / 'dev/data/knowledge/ege_1_6_card_reviews.json').read_text())['cards'] if 'lexicalSourceReview' in r}

    def card(self, r):
        return json.loads((ROOT / f'data/card_{r["id"]}.json').read_text())

    def test_every_context_sensitive_card_checked(self):
        all_reviews = json.loads((ROOT / 'dev/data/knowledge/ege_1_6_card_reviews.json').read_text())['cards']
        expected = {r['id'] for r in all_reviews if r['task'] == 6 and r.get('contextAssessment') == 'context_sensitive_key_preserved'}
        self.assertEqual(set(self.reviews), expected)
        self.assertEqual(len(expected), 21)
        self.assertEqual(sum(r['lexicalSourceReview']['status'] == 'context_scope_pending' for r in self.reviews.values()), 8)
        for r in self.reviews.values(): self.assertTrue(validate(self.card(r), r, self.sources, self.books))

    def test_changed_key_or_condition_rejected(self):
        r = self.reviews['C50FE5']
        for field in ('answer', 'question'):
            card = self.card(r); card[field] += 'x'
            with self.assertRaises(ValueError): validate(card, r, self.sources, self.books)

    def test_pending_note_cannot_disappear(self):
        r = copy.deepcopy(self.reviews['D52745']); r['lexicalSourceReview'].pop('studentNote')
        with self.assertRaises(ValueError): validate(self.card(r), r, self.sources, self.books)

    def test_stale_web_evidence_rejected(self):
        r = copy.deepcopy(self.reviews['C50FE5']); r['lexicalSourceReview']['grammarEvidence'][0]['textSha256'] = '0' * 64
        with self.assertRaises(ValueError): validate(self.card(r), r, self.sources, self.books)

    def test_excerpt_page_cannot_be_confused_with_original_page(self):
        r = copy.deepcopy(self.reviews['B5E8E4']); r['lexicalSourceReview']['bookEvidence'][0]['excerptPage'] = 3
        with self.assertRaises(ValueError): validate(self.card(r), r, self.sources, self.books)
        r = self.reviews['B5E8E4']; refs = validate(self.card(r), r, self.sources, self.books)
        self.assertTrue(any(ref['url'].endswith('rozental-stylistics-2001.pdf#page=4') and 'с. 63' in ref['label'] for ref in refs))

    def test_unsupported_universal_or_unique_claim_rejected(self):
        for name in ('originalUniversallyForbidden', 'answerUniquenessEstablished', 'oldExplanationsUsedAsEvidence'):
            r = copy.deepcopy(self.reviews['84A09F']); r['lexicalSourceReview'][name] = True
            with self.assertRaises(ValueError): validate(self.card(r), r, self.sources, self.books)

    def test_changed_reviewed_edit_rejected(self):
        r = copy.deepcopy(self.reviews['84A09F']); r['lexicalEdit']['correctedSentence'] += 'x'
        with self.assertRaises(ValueError): validate(self.card(r), r, self.sources, self.books)
