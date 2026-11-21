"""Task-23 verifies every statement with literal passage evidence and both key encodings."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import review_reading_content as review


class ReadingContentReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in review.read_registry()['cards']}

    def card(self, cid):
        return json.loads((ROOT / f'data/card_{cid}.json').read_text())

    def test_every_review_covers_all_five_statements_and_reproduces(self):
        self.assertEqual(len(self.reviews), 71)
        self.assertEqual(sum(len(r['rows']) for r in self.reviews.values()), 355)
        actual = {c['number'] for p in (ROOT / 'data').glob('card_*.json') if review.mapping(c := json.loads(p.read_text()))['task'] == 23}
        self.assertEqual(set(self.reviews), actual)
        for cid, r in self.reviews.items():
            self.assertEqual(len(r['rows']), 5)
            self.assertEqual(review.render(self.card(cid), r), self.card(cid)['explanation'])

    def test_negative_question_selects_false_statements(self):
        r = self.reviews['217D24']
        self.assertEqual(r['selection'], 'not_corresponding')
        self.assertEqual([x['number'] for x in r['rows'] if review.chosen(r, x)], [1, 4])
        self.assertTrue(r['rows'][1]['correspondsToText'])
        self.assertIn('НЕ соответствующие', review.render(self.card(r['id']), r))

    def test_binary_verification_is_not_a_digit_sequence(self):
        r = self.reviews['015DE9']; c = self.card(r['id'])
        self.assertEqual(c['answer'], '15')
        self.assertEqual(c['answer_verify'], '10001')
        c['answer_verify'] = '15'; r = copy.deepcopy(r); r['sourceContentSha256'] = review.frozen(c)
        with self.assertRaises(ValueError): review.validate(c, r)

    def test_incomplete_or_invented_evidence_and_old_explanations_rejected(self):
        r = self.reviews['015DE9']
        for change in [lambda x:x['rows'].pop(), lambda x:x['rows'][0].update(statement='подменённый вариант'), lambda x:x['rows'][0].update(correspondsToText=False), lambda x:x['rows'][0].update(evidence=[]), lambda x:x['rows'][0]['evidence'][0].update(quote='выдуманная цитата'), lambda x:x['rows'][0]['evidence'][0].update(sentence=999), lambda x:x['sourceEvidence'].update(textSha256='bad'), lambda x:x['rewriteReview'].update(oldExplanationsUsedAsEvidence=True), lambda x:x.update(selection='not_corresponding')]:
            broken = copy.deepcopy(r); change(broken)
            with self.assertRaises(ValueError): review.validate(self.card(r['id']), broken)

    def test_context_supports_the_accepted_inference(self):
        r = self.reviews['1DC0F3']
        card = self.card(r['id'])
        self.assertFalse(r.get('sourceReviewPending'))
        self.assertEqual(card['answer'], '145')
        self.assertNotIn('Требует уточнения', card['explanation'])
        self.assertIn('подразумевается', r['rows'][3]['reason'])
        broken = copy.deepcopy(r)
        broken.update(sourceReviewPending=True, sourceReviewNote='Повторная проверка')
        with self.assertRaises(ValueError): review.validate(self.card(r['id']), broken)

    def test_distractors_preserve_time_speaker_and_group_distinctions(self):
        self.assertIn('девятнадцать', self.reviews['09E9D2']['rows'][4]['reason'])
        self.assertIn('Саша', self.reviews['30D60A']['rows'][0]['reason'])
        self.assertIn('полковник', self.reviews['2EF1B4']['rows'][3]['reason'])
        self.assertIn('Книппер', self.reviews['1618E6']['rows'][2]['reason'])

    def test_restored_bracket_is_present_in_all_copies_of_the_passage(self):
        for cid in ['8BD010', '71FF7C', 'A974B4', 'C590CF', 'CB7468']:
            card = self.card(cid)
            raw = card['text']
            self.assertIn('(40)Минут через пятнадцать', raw)
            ss = review.sentences(card)
            self.assertEqual(len(ss), 48)
            self.assertEqual(ss[39], 'Минут через пятнадцать мы достигли леса и остановились.')
        card['text'] = raw.replace('(40)Минут', '(40Минут')
        with self.assertRaises(ValueError):
            review.sentences(card)
