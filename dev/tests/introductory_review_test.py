"""Task-18 address, introductory words and nonintroductory lookalikes."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import review_introductory_explanations as introductory
from handbook_fb2 import read_handbook


class IntroductoryReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in introductory.read_registry()['cards']}
        _, ps = read_handbook(ROOT / 'data/knowledge/sources/lopatin-2007.fb2.zip')
        cls.ps = {p['id']:p for p in ps}

    def card(self, cid):
        return json.loads((ROOT / f'data/card_{cid}.json').read_text())

    def test_all_positions_reproduce_published_explanations(self):
        self.assertEqual(len(self.reviews), 85)
        for cid, review in self.reviews.items():
            self.assertEqual(introductory.render(self.card(cid), review, self.ps), self.card(cid)['explanation'])

    def test_pronouns_are_subjects_and_o_belongs_to_address(self):
        r = self.reviews['0187D6']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Где ты, далёкий друг?', text)
        self.assertIn('Где вы, дни радостей?', text)
        self.assertIn('назад, О время прежнее, о время незабвенно?', text)
        self.assertTrue(text.endswith('(В.А. Жуковский)'))

    def test_address_and_probability_have_distinct_boundaries(self):
        r = self.reviews['037608']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Я вам, Алёна Ивановна, на днях, может быть, ещё', text)

    def test_however_and_as_if_are_not_introductory_here(self):
        r = self.reviews['06C21C']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('университете, однако это желание', text)
        self.assertIn('котором, к сожалению, не оставляло', text)
        r = self.reviews['08F8A1']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('как будто тает', text)
        self.assertNotIn('как будто,', text)

    def test_introductory_word_inside_participle_phrase_is_separate(self):
        r = self.reviews['03DC1B']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('современников, два', text)
        self.assertIn('ставшие, кстати, очень известными учёными', text)
        self.assertIn('lopatin-2007-punctuation-93', r['rows'][1]['sourceIds'])

    def test_akh_interjection_has_direct_handbook_example(self):
        r = self.reviews['2F6560']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Ах, поля мои, борозды милые, Хороши вы', text)
        self.assertIn('lopatin-2007-punctuation-103', r['rows'][0]['sourceIds'])
        self.assertIn('борозды милые', self.ps['lopatin-2007-punctuation-103']['body'])

    def test_lookalike_predicate_and_nested_introductory_phrase_differ(self):
        r = self.reviews['2B147E']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Этот человек кажется очень уставшим.', text)
        self.assertIn('Он, видимо, сегодня много работал и, по-моему, сейчас заснёт.', text)
        r = self.reviews['493DA7']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('(Что, может быть, одно и то же)', text)
        self.assertIn('спаси нас, Боже!', text)

    def test_similarity_and_location_predicates_are_not_introductory(self):
        r = self.reviews['8DDA2F']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Озеро, похоже, было бесконечным.', text)
        self.assertIn('оно было похоже на вытянутую во всю длину ленту.', text)
        r = self.reviews['64C915']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('и затем оказывается во фруктовом саду.', text)

    def test_address_definition_stays_together_and_pronoun_stays_subject(self):
        r = self.reviews['8A27AE']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Вернись, былое зренье!', text)
        self.assertIn('Земля, пошли мне', text)
        r = self.reviews['821308']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Как хороши вы в лучах золотых', text)
        self.assertIn('печальны вы, капли ненастные, Осенью', text)

    def test_completeness_matches_every_actual_task18_card(self):
        from exam_2027 import mapping
        ids = set()
        for path in (ROOT / 'data').glob('card_*.json'):
            card = json.loads(path.read_text())
            if mapping(card)['task'] == 18:
                ids.add(card['number'])
        self.assertEqual(set(self.reviews), ids)

    def test_standalone_exclamations_differ_from_pronoun_subjects(self):
        r = self.reviews['D8217D']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Ты, земля! И вы, равнин пески!', text)
        self.assertIn('Я не в силах скрыть', text)
        r = self.reviews['FDD6B0']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Тебя волшебник искушал;', text)
        self.assertIn('Нет, нет, мой друг, мечты ревнивой', text)
        self.assertIn('Мне долго счастье чуждо было.', text)

    def test_same_source_phrase_can_be_sentence_member(self):
        r = self.reviews['FA6E37']
        text = introductory.validate(self.card(r['id']), r, self.ps)
        self.assertIn('Май, по словам старожилов,', text)
        self.assertIn('судить о климате по словам старожилов нельзя.', text)
        self.assertEqual(text.count(','), 3)

    def test_wrong_task_and_changed_key_or_source_rejected(self):
        original = self.reviews['0187D6']
        for mutate in (lambda r:r.update(task=17), lambda r:r['rows'][0].update(comma=True), lambda r:r['paragraphEvidence'][0].update(textSha256='0' * 64)):
            r = copy.deepcopy(original)
            mutate(r)
            with self.assertRaises(ValueError):
                introductory.validate(self.card(r['id']), r, self.ps)


if __name__ == '__main__':
    unittest.main()
