"""Task-17 reviews cover every original numbered position and preserve inputs."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import review_isolation_explanations as isolation
from handbook_fb2 import read_handbook


class IsolationReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in isolation.read_registry()['cards']}
        _, ps = read_handbook(ROOT / 'data/knowledge/sources/lopatin-2007.fb2.zip')
        cls.ps = {p['id']:p for p in ps}

    def card(self, cid):
        return json.loads((ROOT / f'data/card_{cid}.json').read_text())

    def test_all_positions_reproduce_published_explanations(self):
        self.assertEqual(len(self.reviews), 89)
        for cid, review in self.reviews.items():
            self.assertEqual(isolation.render(self.card(cid), review, self.ps), self.card(cid)['explanation'])

    def test_union_of_gerund_phrases_has_no_internal_comma(self):
        r = self.reviews['0031E9']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('лидеров и тщательно готовясь', text)
        self.assertIn('новые участники, глядя', text)
        self.assertIn('этапу, стремились', text)

    def test_conjunction_stays_outside_gerund_phrase(self):
        r = self.reviews['0BBE73']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('запер дверь и, вернувшись к столу, сел', text)
        self.assertIn('Рудина, тихонько опершись', text)

    def test_nested_attributes_share_right_boundary(self):
        r = self.reviews['0B26A4']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('понятием, существовавшим в мире до неё, свидетельствовала', text)
        self.assertEqual(text.count(','), 3)

    def test_detached_attribute_refers_to_sosny_not_sun(self):
        r = self.reviews['25D27A']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Торжествуя и смеясь, катилось', text)
        self.assertIn('сосен, обрамляющих околицу, солнце, обещая', text)

    def test_multiple_nested_phrases_share_one_closing_comma(self):
        r = self.reviews['29032E']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Эфесу и, посетив храм Артемиды, восстанавливающийся после пожара, устроенного Геростратом, решил', text)
        self.assertEqual(text.count(','), 4)

    def test_conjunction_between_gerund_phrases_has_no_surrounding_commas(self):
        r = self.reviews['3F2942']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('в брызгавшую росой луговую траву', text)
        self.assertIn('метёлками и улыбаясь', text)
        self.assertEqual(text.count(','), 1)

    def test_nested_river_attribute_has_shared_right_boundary(self):
        r = self.reviews['60D8CE']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Арагва, слившись с горной рекой, шумно вырывающейся из полного мглою ущелья, тянется', text)
        self.assertEqual(text.count(','), 3)

    def test_inner_and_outer_conjunctions_in_fern_sentence_differ(self):
        r = self.reviews['8BDD2D']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('папоротников, уже окрашенных осенними красками, заполонили', text)
        self.assertIn('рощу, бесконечно путаясь и пересекаясь, и сверкали', text)
        self.assertEqual(text.count(','), 4)

    def test_outer_action_conjunction_differs_from_inner_gerund_conjunction(self):
        r = self.reviews['A6C1C2']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('не отвечала ему и, слегка приподняв брови и краснея, глядела', text)
        self.assertEqual(text.count(','), 2)

    def test_adjacent_attribute_and_gerund_share_boundary(self):
        r = self.reviews['C57B05']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Солнце, тысячекратно отражённое рябью моря, гармонично сливаясь в единое целое, было наполнено', text)
        self.assertEqual(text.count(','), 3)

    def test_completeness_matches_every_actual_task17_card(self):
        from exam_2027 import mapping
        ids = set()
        for path in (ROOT / 'data').glob('card_*.json'):
            card = json.loads(path.read_text())
            if mapping(card)['task'] == 17:
                ids.add(card['number'])
        self.assertEqual(set(self.reviews), ids)

    def test_comparative_word_is_inside_gerund_group(self):
        r = self.reviews['FFA9CC']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('скал, будто чувствуя приближение нового дня и пугаясь его', text)
        self.assertEqual(text.count(','), 3)
        r = self.reviews['F51C92']
        text = isolation.validate(self.card(r['id']), r, self.ps)
        self.assertIn('факторов, связанных со спецификой научного мышления, отличается от', text)
        self.assertEqual(text.count(','), 3)

    def test_missing_position_changed_key_and_stale_evidence_rejected(self):
        original = self.reviews['0031E9']
        for mutate in (lambda r:r['rows'].pop(), lambda r:r['rows'][0].update(comma=False), lambda r:r['paragraphEvidence'][0].update(textSha256='0' * 64), lambda r:r.update(markedSentence=r['markedSentence'][1:])):
            r = copy.deepcopy(original)
            mutate(r)
            with self.assertRaises(ValueError):
                isolation.validate(self.card(r['id']), r, self.ps)


if __name__ == '__main__':
    unittest.main()
