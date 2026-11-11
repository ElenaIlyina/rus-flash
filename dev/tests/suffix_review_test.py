#!/usr/bin/env python3
"""New suffix reviews cover every task-11 form without trusting old explanations."""
import copy
import json
import re
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "dev/scripts"))
from exam_2027 import mapping
from review_prefix_explanations import render


class SuffixReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r["id"]: r for r in json.loads(
            (ROOT / "dev/data/knowledge/suffix_card_reviews.json").read_text())["cards"]}
        cls.cards = {c["number"]: c for f in (ROOT / "data").glob("card_*.json")
                     for c in [json.loads(f.read_text())]}

    def test_all_task_11_cards_have_new_complete_reviews(self):
        expected = {cid for cid, c in self.cards.items() if mapping(c)["task"] == 11}
        self.assertEqual(set(self.reviews), expected)
        self.assertEqual(len(expected), 73)
        for cid, review in self.reviews.items():
            with self.subTest(card=cid):
                self.assertTrue(review["rewriteReview"]["previousExplanationNotTrusted"])
                self.assertFalse(review["rewriteReview"]["independentSubjectAcceptance"])
                self.assertEqual(len(review["rows"]), len(self.cards[cid]["variants"]))
                self.assertTrue(review["hint"])
                self.assertEqual(render(self.cards[cid], review), self.cards[cid]["explanation"])

    def test_single_word_form_uses_requested_letter_and_rejects_a_second_match(self):
        review = self.reviews["0939F2"]
        text = render(self.cards["0939F2"], review)
        self.assertIn("Ответ: назойливый", text)
        self.assertIn("Слово 1", text)
        self.assertNotIn("Выбираем ряд", text)
        wrong = copy.deepcopy(review)
        wrong["rows"][0]["words"] = ["замшивый"]
        with self.assertRaisesRegex(ValueError, "exactly one"):
            render(self.cards["0939F2"], wrong)

    def test_accented_sources_and_words_without_an_inserted_letter(self):
        text = render(self.cards["31C333"], self.reviews["31C333"])
        self.assertIn("черешенка", re.sub("<[^>]+>", "", text))
        self.assertIn("ковш", text)
        for cid, word in [("3048D8", "немецкий"), ("63ECF5", "моряцкий")]:
            with self.subTest(card=cid):
                self.assertIn(word, render(self.cards[cid], self.reviews[cid]))
                self.assertTrue(any(0 in row.get("gapWidths", []) for row in self.reviews[cid]["rows"]))

    def test_context_and_verb_exceptions_are_explained(self):
        for cid, text in [("15E718", "силой ветра"), ("C22C7B", "характеристика погоды"),
                          ("D310F9", "лишить силы другого"), ("239905", "самому стать бессильным"),
                          ("7D0DF1", "II спряжения"), ("482BB0", "особый список")]:
            with self.subTest(card=cid):
                self.assertIn(text, self.cards[cid]["explanation"])


if __name__ == "__main__":
    unittest.main()
