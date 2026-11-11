#!/usr/bin/env python3
"""Exercise format, empty-gap, source integrity, and dictionary reproduction checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "dev/scripts"))
sys.path.insert(0, str(ROOT / "dev/scripts/content"))
from exam_2027 import mapping
from handbook_fb2 import read_handbook
from review_prefix_explanations import render, validate_rule_evidence
from unpack_mobi7_dictionary import indexed_dictionary
from extract_mobi_articles import extract


class PrefixCompletionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {e["id"]: e for e in json.loads(
            (ROOT / "dev/data/knowledge/prefix_card_reviews.json").read_text())["cards"]}
        cls.cards = {c["number"]: c for file in (ROOT / "data").glob("card_*.json")
                     for c in [json.loads(file.read_text())]}
        _, paragraphs = read_handbook(ROOT / "data/knowledge/sources/lopatin-2007.fb2.zip")
        cls.paragraphs = {p["id"]: p for p in paragraphs}

    def test_all_task_10_cards_have_fresh_reviews_and_individual_hints(self):
        expected = {cid for cid, card in self.cards.items() if mapping(card)["task"] == 10}
        self.assertEqual(set(self.reviews), expected)
        for cid, review in self.reviews.items():
            with self.subTest(card=cid):
                self.assertTrue(review["rewriteReview"]["previousExplanationNotTrusted"])
                self.assertFalse(review["rewriteReview"]["independentSubjectAcceptance"])
                self.assertGreater(len(review["hint"]), 100)
                self.assertEqual(render(self.cards[cid], review), self.cards[cid]["explanation"])
                validate_rule_evidence(review, self.paragraphs)

    def test_word_pair_answer_is_words_and_requires_one_row(self):
        card, review = self.cards["073234"], self.reviews["073234"]
        text = render(card, review)
        self.assertIn("Ответ: беспомощный сгорел", text)
        self.assertIn("а не номер ряда", text)
        wrong = copy.deepcopy(review)
        wrong["rows"][0]["words"] = ["преграда", "преютить"]
        with self.assertRaisesRegex(ValueError, "exactly one"):
            render(card, wrong)

    def test_no_letter_is_explicit_and_never_a_matching_letter(self):
        for cid, word in [("D30EAB", "детясли"), ("CF4C4A", "контрудар")]:
            with self.subTest(card=cid):
                review = self.reviews[cid]
                text = render(self.cards[cid], review)
                self.assertIn(word, text)
                self.assertIn("буква не вставляется", text)
                self.assertEqual(review["rows"][3]["gapWidths"], [1, 1, 0])
                wrong = copy.deepcopy(review)
                del wrong["rows"][3]["gapWidths"]
                with self.assertRaisesRegex(ValueError, "does not fit"):
                    render(self.cards[cid], wrong)

    def test_stale_source_fingerprint_and_missing_evidence_are_rejected(self):
        review = copy.deepcopy(self.reviews["D30EAB"])
        review["rows"][3]["sourceEvidence"][0]["textSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Stale rule evidence"):
            validate_rule_evidence(review, self.paragraphs)
        review = copy.deepcopy(self.reviews["D30EAB"])
        review["rows"][3]["sourceEvidence"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete rule evidence"):
            validate_rule_evidence(review, self.paragraphs)

    def test_every_published_mobi_article_reproduces_from_pinned_source(self):
        articles = json.loads((ROOT / "data/sources/ozhegov-shvedova.json").read_text())["entries"]
        choices = {a["headword"]: a["sourceHeadword"] for a in articles if a.get("sourceHeadword")}
        indexed = indexed_dictionary(ROOT / "dev/docs/references/ozhegov-shvedova-user-mobi/source.mobi")
        extracted = {a["headword"]: a for a in extract(indexed, {a["headword"] for a in articles}, choices)}
        for article in articles:
            with self.subTest(headword=article["headword"]):
                self.assertEqual(article, extracted[article["headword"]])

    def test_mobi_reader_rejects_wrong_profile_before_decoding(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "wrong.mobi"
            path.write_bytes(b"not a dictionary")
            with self.assertRaisesRegex(ValueError, "Unsupported dictionary size"):
                indexed_dictionary(path)


if __name__ == "__main__":
    unittest.main()
