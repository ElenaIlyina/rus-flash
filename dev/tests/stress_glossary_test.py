import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
from card_data import load_cards
from exam_2027 import mapping, text
from stress_glossary import validate_glossary, normalize, glossary_text

class StressGlossaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT/'data/knowledge/stress-glossary.json').read_text())
        cls.cards = load_cards()

    def test_every_option_is_covered_with_its_reviewed_stress(self):
        validate_glossary(self.data, self.cards, mapping, text)
        self.assertEqual((self.data['cardCount'], self.data['wordCount']), (114,193))
        words = {w['id']:w for w in self.data['words']}
        reviews = json.loads((ROOT/'dev/data/knowledge/ege_1_6_card_reviews.json').read_text())['cards']
        total = 0
        options = []
        for card in reviews:
            if card['task']!=4:continue
            for row in card['stressReview']['options']:
                total += 1
                wid = normalize(row['normativeForm'])
                self.assertEqual(words[wid]['form'], row['normativeForm'])
                options.append({'wordId':wid,'cardId':card['id'],'part':row['number'],'evidenceType':row['evidenceType']})
        self.assertEqual(total, 570)
        evidence = json.loads((ROOT/'dev/docs/content-audit/stress-glossary-evidence.json').read_text())
        self.assertEqual(evidence['options'], options)
        for word in words.values():self.assertIn(word['form'], glossary_text(self.data))

    def test_build_rejects_missing_forms_groups_or_wrong_card_links(self):
        bad = copy.deepcopy(self.data);bad['words'].pop()
        with self.assertRaises(ValueError):validate_glossary(bad,self.cards,mapping,text)
        bad = copy.deepcopy(self.data);bad['parts'][0]['groups'][0]['wordIds'].pop()
        with self.assertRaises(ValueError):validate_glossary(bad,self.cards,mapping,text)
        bad = copy.deepcopy(self.data);bad['words'][0]['cardIds']=[]
        with self.assertRaises(ValueError):validate_glossary(bad,self.cards,mapping,text)
        bad = copy.deepcopy(self.data);bad['words'][0]['form']=bad['words'][0]['form'].lower()
        with self.assertRaises(ValueError):validate_glossary(bad,self.cards,mapping,text)

    def test_comparison_groups_keep_related_forms_together(self):
        groups = [set(g['wordIds']) for p in self.data['parts'] for g in p['groups']]
        for family in [{'ногтя','ногтей'}, {'торты','тортов'}, {'звонит','звонишь','звоним'},
                       {'дозировать','пломбировать','опломбировать'}, {'бралась','кралась'}]:
            self.assertTrue(any(family<=group for group in groups), family)

if __name__=='__main__':unittest.main()
