"""All modern task 1–4 cards have contextual reviews, not just answer keys."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from exam_2027 import mapping


class ModernTextReviewTest(unittest.TestCase):
    def test_every_modern_card_has_matching_review_and_five_reasoned_options(self):
        reviews={e['id']:e for e in json.loads((ROOT/'dev/data/knowledge/ege_1_6_card_reviews.json').read_text())['cards']}
        for p in (ROOT/'data').glob('card_*.json'):
            card=json.loads(p.read_text());position=mapping(card)
            if position['task'] not in {1,2,3,4} or position['formatStatus']=='historical_format':continue
            with self.subTest(card=card['number']):
                review=reviews[card['number']]
                self.assertTrue(review['hint'])
                self.assertEqual(review['explanationSha256'],hashlib.sha256(card['explanation'].encode()).hexdigest())
                if position['task'] in {2,3}:
                    rows=review['lexicalReview' if position['task']==2 else 'styleReview']['options']
                    self.assertEqual([r['number'] for r in rows],[1,2,3,4,5])
                    self.assertEqual(''.join(str(r['number']) for r in rows if r['keySelects']),card['answer'])
                    self.assertTrue(all(r['reason'] for r in rows))
                    self.assertTrue(review['dictionaryReview']['sourceRefs'])

    def test_nonliteral_meanings_and_dictionary_qualifications_are_explained(self):
        cards={cid:json.loads((ROOT/f'data/card_{cid}.json').read_text()) for cid in ['019533','6BDFBD','E2313B','0B0920','BF9751']}
        self.assertIn('Разности электрических потенциалов',cards['019533']['explanation'])
        self.assertIn('не должны вестись',cards['6BDFBD']['explanation'])
        self.assertIn('яркая окраска цветка',cards['E2313B']['explanation'])
        self.assertIn('«прост.»',cards['0B0920']['explanation'])
        self.assertIn('повторяется местоимение «его»',cards['BF9751']['explanation'])
        self.assertIn('content_issue',cards['E2313B'])


if __name__=='__main__':unittest.main()
