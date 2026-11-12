"""Task-19 clause boundaries are not the positions of isolated relative words."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import review_subordination_explanations as subordination
from handbook_fb2 import read_handbook


class SubordinationReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in subordination.read_registry()['cards']}
        _, ps = read_handbook(ROOT / 'data/knowledge/sources/lopatin-2007.fb2.zip')
        cls.ps = {p['id']:p for p in ps}

    def card(self, cid):
        return json.loads((ROOT / f'data/card_{cid}.json').read_text())

    def test_all_positions_reproduce_published_explanations(self):
        self.assertEqual(len(self.reviews), 126)
        for cid, review in self.reviews.items():
            self.assertEqual(subordination.render(self.card(cid), review, self.ps), self.card(cid)['explanation'])

    def test_relative_phrase_starts_before_relative_word(self):
        r = self.reviews['04CDD2']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('сад, характерным признаком которого является простота, получает', text)
        self.assertEqual(text.count(','), 2)
        r = self.reviews['0758F7']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('формул, многие из которых позволяют', text)
        self.assertEqual(text.count(','), 1)

    def test_fronted_infinitive_stays_inside_relative_clause(self):
        r = self.reviews['0F6162']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('вопросы, дать ответы на которые может только время', text)
        self.assertEqual(text.count(','), 1)

    def test_condition_and_relative_clause_have_separate_boundaries(self):
        r = self.reviews['1037E2']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('стаи теряются, они издают громкие свистовые крики, благодаря которым им удаётся', text)
        self.assertEqual(text.count(','), 2)

    def test_homogeneous_temporal_clauses_share_single_when(self):
        r = self.reviews['120B1C']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('когда над нашими головами разразилась гроза и лес точно застонал', text)
        self.assertIn('огонёк, свет от которого осветил', text)
        self.assertEqual(text.count(','), 3)
        self.assertIn('lopatin-2007-punctuation-119', r['rows'][2]['sourceIds'])

    def test_relative_clauses_and_nested_condition_have_distinct_structure(self):
        r = self.reviews['160938']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('определители, в которых дают характеристики пернатым и которые значительно', text)
        self.assertEqual(text.count(','), 2)
        r = self.reviews['16BE17']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('поняли, что они сбились с пути, перед их взором', text)
        self.assertIn('край которого уходил в необозримую даль и смыкался', text)
        self.assertEqual(text.count(','), 3)

    def test_completeness_matches_every_actual_task19_card(self):
        from exam_2027 import mapping
        ids = set()
        for path in (ROOT / 'data').glob('card_*.json'):
            card = json.loads(path.read_text())
            if mapping(card)['task'] == 19:
                ids.add(card['number'])
        self.assertEqual(set(self.reviews), ids)

    def test_author_resolved_clause_closes_before_main_predicate(self):
        r = self.reviews['F22DF5']
        card = self.card(r['id'])
        text = subordination.render(card, r, self.ps)
        self.assertEqual(card['answer'], '2356')
        self.assertFalse(r['sourceReviewPending'])
        self.assertNotIn('Трактовка требует уточнения', text)
        self.assertNotIn('Возможное исправление:', text)
        self.assertIn('мальчишкой, и обращался', text)
        self.assertIn('только к не скрывал', text)
        changed = copy.deepcopy(r)
        changed['sourceReviewPending'] = True
        with self.assertRaises(ValueError):
            subordination.validate(card, changed, self.ps)

    def test_double_conditional_conjunction_differs_from_single(self):
        r = self.reviews['78F219']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('подумали, что если', text)
        r = self.reviews['E40443']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('решили, что, если', text)
        self.assertIn('через день, придётся', text)

    def test_boundary_of_infinitive_group_and_nested_explanation(self):
        r = self.reviews['2C868D']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('определить, какой это маяк, и узнать, где находится корабль', text)
        r = self.reviews['6F2723']
        text = subordination.validate(self.card(r['id']), r, self.ps)
        self.assertIn('уселся дом, и той горы, что напротив нас, не были', text)

    def test_wrong_task_changed_key_or_partial_marked_sentence_rejected(self):
        original = self.reviews['04CDD2']
        for mutate in (lambda r:r.update(task=18), lambda r:r['rows'][1].update(comma=True), lambda r:r.update(markedSentence=r['markedSentence'][1:])):
            r = copy.deepcopy(original)
            mutate(r)
            with self.assertRaises(ValueError):
                subordination.validate(self.card(r['id']), r, self.ps)


if __name__ == '__main__':
    unittest.main()
