"""Task-24 keeps all referenced sentences, original keys and explicit source limits."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import review_discourse as review


class DiscourseReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in review.read_registry()['cards']}
        cls.sources = review.load_sources()

    def card(self, cid):
        return json.loads((ROOT / f'data/card_{cid}.json').read_text())

    def test_all_prepared_reviews_reproduce_all_five_statements(self):
        self.assertGreaterEqual(len(self.reviews), 20)
        for cid, r in self.reviews.items():
            self.assertEqual(len(r['rows']), 5)
            self.assertEqual(review.render(self.card(cid), r, self.sources), self.card(cid)['explanation'])

    def test_erroneous_question_selects_false_judgments(self):
        r = self.reviews['34DD9B']
        self.assertEqual(r['selection'], 'incorrect')
        self.assertEqual([row['number'] for row in r['rows'] if review.chosen(r, row)], [2, 5])
        self.assertEqual(review.selection({'question':'Какие утверждения являются неверными?'}), 'incorrect')
        self.assertIn('ОШИБОЧНЫЕ', review.render(self.card(r['id']), r, self.sources))

    def test_range_coverage_cannot_skip_an_interior_sentence(self):
        r = copy.deepcopy(self.reviews['044054'])
        r['rows'][0]['evidence'] = [e for e in r['rows'][0]['evidence'] if e['sentence'] != 8]
        with self.assertRaises(ValueError): review.validate(self.card(r['id']), r, self.sources)
        self.assertEqual(review.referenced_numbers('В предложениях 7‒10 дано описание.'), {7,8,9,10})

    def test_quote_key_and_old_explanation_evidence_cannot_be_substituted(self):
        r = self.reviews['011D96']
        for change in [lambda x:x['rows'].pop(), lambda x:x['rows'][0].update(isCorrect=False), lambda x:x['rows'][0].update(statement='подменённое утверждение'), lambda x:x['rows'][0]['evidence'][0].update(quote='выдуманная цитата'), lambda x:x['rewriteReview'].update(oldExplanationsUsedAsEvidence=True)]:
            broken = copy.deepcopy(r); change(broken)
            with self.assertRaises(ValueError): review.validate(self.card(r['id']), broken, self.sources)
        c = self.card(r['id']); c['answer_verify'] = c['answer']; broken = copy.deepcopy(r); broken['sourceContentSha256'] = review.frozen(c)
        with self.assertRaises(ValueError): review.validate(c, broken, self.sources)

    def test_theory_is_criteria_with_verified_page_evidence(self):
        r = self.reviews['011D96']
        for change in [lambda x:x['theoryEvidence'].pop(), lambda x:x['theoryEvidence'][0].update(textSha256='bad'), lambda x:x.update(theoryScope='fipi_answer_key')]:
            broken = copy.deepcopy(r); change(broken)
            with self.assertRaises(ValueError): review.validate(self.card(r['id']), broken, self.sources)
        self.assertIn(self.sources['citationLabel'], review.render(self.card(r['id']), r, self.sources))

    def test_pending_interpretation_must_remain_visible_and_logged(self):
        r = self.reviews['24EAE1']
        self.assertTrue(r['sourceReviewPending'])
        self.assertIn(r['sourceReviewNote'], review.render(self.card(r['id']), r, self.sources))
        broken = copy.deepcopy(r); broken['sourceReviewPending'] = False
        with self.assertRaises(ValueError): review.validate(self.card(r['id']), broken, self.sources)

    def test_saved_page_evidence_works_without_external_materials_directory(self):
        with mock.patch.object(Path, 'is_file', return_value=False):
            sources = review.load_sources()
        self.assertEqual(sources, self.sources)
