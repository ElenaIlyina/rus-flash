#!/usr/bin/env python3
"""Task-12 coverage and source-confirmed exceptional paradigms."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "dev/scripts"))
from exam_2027 import mapping
from review_prefix_explanations import render


class VerbReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r["id"]: r for r in json.loads(
            (ROOT / "dev/data/knowledge/verb_card_reviews.json").read_text())["cards"]}
        cls.cards = {c["number"]: c for f in (ROOT / "data").glob("card_*.json")
                     for c in [json.loads(f.read_text())]}

    def test_every_task_12_card_has_a_fresh_complete_review(self):
        expected = {cid for cid, c in self.cards.items() if mapping(c)["task"] == 12}
        self.assertEqual(set(self.reviews), expected)
        self.assertEqual(len(expected), 70)
        for cid, review in self.reviews.items():
            with self.subTest(card=cid):
                self.assertTrue(review["rewriteReview"]["previousExplanationNotTrusted"])
                self.assertFalse(review["rewriteReview"]["independentSubjectAcceptance"])
                self.assertTrue(review["hint"])
                self.assertEqual(render(self.cards[cid], review), self.cards[cid]["explanation"])

    def test_target_yu_and_explicit_source_stress_glyph(self):
        text = render(self.cards["72ADD4"], self.reviews["72ADD4"])
        self.assertIn("Ответ: присыплют", text)
        review = self.reviews["5D3551"]
        self.assertEqual(review["rows"][2]["accentGlyphs"][0]["from"], "á")
        self.assertIn("признá..шься", self.cards["5D3551"]["variants"][2])
        self.assertIn("призна", render(self.cards["5D3551"], review))
        wrong = copy.deepcopy(review)
        wrong["rows"][2]["accentGlyphs"][0]["to"] = "о"
        with self.assertRaisesRegex(ValueError, "Unsupported explicit accent"):
            render(self.cards["5D3551"], wrong)

    def test_exact_dictionary_paradigms_are_not_conflated(self):
        words = {e["word"]: e for r in self.reviews.values() for row in r["rows"] for e in row["wordEvidence"]}
        self.assertEqual(words["свищет"]["lemma"], "свистать")
        self.assertEqual(words["засвищут"]["lemma"], "засвистать")
        self.assertEqual(words["блещущий"]["lemma"], "блестеть")
        self.assertEqual(words["блещущий"]["grammaticalFamily"], "present_active_variant")
        self.assertTrue(words["блещущий"]["dictionaryEntryIds"])
        self.assertEqual(words["движимый"]["grammaticalFamily"], "passive_exception")
        self.assertEqual(words["движущийся"]["grammaticalFamily"], "present_active")

    def test_unsupported_curtain_interpretation_is_not_published(self):
        for cid in ["2081B3", "5D3551"]:
            text = render(self.cards[cid], self.reviews[cid])
            self.assertIn("занавесить", text)
            self.assertNotIn("незанавешанный", text)
            self.assertNotIn("wordAlternatives", self.reviews[cid]["rows"][1])


if __name__ == "__main__":
    unittest.main()
