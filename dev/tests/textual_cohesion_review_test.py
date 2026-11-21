"""Protect task-26 condition coverage, adjacent evidence and unresolved alternatives."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import review_textual_cohesion as review


class TextualCohesionReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in review.read_registry()['cards']}
        cls.sources = review.load_sources()

    def card(self, cid):
        return json.loads((ROOT / f'data/card_{cid}.json').read_text())

    def test_complete_task_has_reproducible_public_explanations(self):
        self.assertEqual(len(self.reviews), 71)
        for cid, entry in self.reviews.items():
            with self.subTest(card=cid):
                self.assertEqual(review.render(self.card(cid), entry, self.sources), self.card(cid)['explanation'])

    def test_all_kinds_are_required_by_condition_not_just_declared_by_review(self):
        r = copy.deepcopy(self.reviews['694236'])
        self.assertEqual(review.requested_kinds(self.card(r['id'])), {'determinative','demonstrative','word_form','synonym'})
        r['requestedKinds'].remove('word_form')
        r['links'] = [link for link in r['links'] if link['kind'] != 'word_form']
        with self.assertRaises(ValueError): review.validate(self.card(r['id']), r, self.sources)

    def test_range_and_previous_context_cannot_be_skipped_or_duplicated(self):
        r = self.reviews['0121C7']
        for change in [lambda x:x['evidence'].pop(0), lambda x:x['evidence'].pop(3), lambda x:x['evidence'].append(copy.deepcopy(x['evidence'][0]))]:
            broken = copy.deepcopy(r); change(broken)
            with self.assertRaises(ValueError): review.validate(self.card(r['id']), broken, self.sources)
        first = self.reviews['38150E']
        self.assertEqual(first['evidence'][0]['sentence'], 1)
        self.assertEqual(review.target_numbers(self.card(first['id'])), set(range(1,9)))

    def test_each_selected_sentence_needs_its_own_adjacent_links(self):
        r = self.reviews['66262F']
        self.assertEqual(r['answerNumbers'], [33,36])
        for change in [lambda x:x.update(links=[link for link in x['links'] if link['sentence'] != 36]), lambda x:x['links'][0].update(previousSentence=31)]:
            broken = copy.deepcopy(r); change(broken)
            with self.assertRaises(ValueError): review.validate(self.card(r['id']), broken, self.sources)

    def test_citations_conditions_and_sources_cannot_be_substituted(self):
        r = self.reviews['694236']
        for change in [lambda x:x['links'][0].update(token='выдумка'), lambda x:x['evidence'][0].update(quote='выдуманная цитата'), lambda x:x['theoryEvidence'][0].update(textSha256='bad'), lambda x:x['rewriteReview'].update(oldExplanationsUsedAsEvidence=True)]:
            broken = copy.deepcopy(r); change(broken)
            with self.assertRaises(ValueError): review.validate(self.card(r['id']), broken, self.sources)

    def test_preserved_key_and_resolved_review_flags(self):
        pending = [r for r in self.reviews.values() if r.get('sourceReviewPending')]
        self.assertEqual(pending, [])
        broken = copy.deepcopy(self.reviews['BA3A4B'])
        broken.update(sourceReviewPending=True, sourceReviewNote='Повторная проверка')
        with self.assertRaises(ValueError): review.validate(self.card(broken['id']), broken, self.sources)
        r = copy.deepcopy(self.reviews['682A9C']); r['answerNumbers'] = [2]
        with self.assertRaises(ValueError): review.validate(self.card(r['id']), r, self.sources)

    def test_rewritten_682A9C_is_no_longer_blocked_by_its_old_header_conflict(self):
        overrides = json.loads((ROOT/'dev/data/content_review_overrides.json').read_text())['cards']
        self.assertNotIn('682A9C', overrides)
        catalog = json.loads((ROOT/'html/assets/data/catalog.json').read_text())['cards']
        self.assertTrue(next(c for c in catalog if c['id']=='682A9C')['eligibleForProgress'])
        self.assertEqual(self.reviews['682A9C']['answerNumbers'], [2,6])

    def test_numeric_footnote_is_not_lost_or_reinterpreted_as_word_ending(self):
        r = self.reviews['38150E']
        self.assertIn('сопки3', next(e['quote'] for e in r['evidence'] if e['sentence'] == 3))
        link = next(link for link in r['links'] if link['token'] == 'сопки')
        self.assertEqual(link['antecedent'], 'сопки3')
        self.assertIn('номер сноски', link['reason'])
