#!/usr/bin/env python3
"""Task 6: exact source freeze, edit operation, key and traceable evidence."""
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0,str(ROOT/'dev/scripts'))
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0, str(ROOT / 'scripts'))
from generate_manifest import load_cards
from exam_2027 import mapping
from paronym_sources import validate_sources, publication_ready


class LexicalNormsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards = {c['number']:c for c in load_cards() if mapping(c)['task']==6}
        cls.reviews = {r['id']:r for r in json.loads((ROOT/'dev/data/knowledge/ege_1_6_card_reviews.json').read_text())['cards'] if r['task']==6}
        cls.sources = validate_sources(json.loads((ROOT/'dev/data/knowledge/paronyms.json').read_text()), ROOT)

    def test_all_cards_have_frozen_sources_and_current_explanations(self):
        self.assertEqual(len(self.cards),67)
        self.assertEqual(self.cards.keys(),self.reviews.keys())
        for cid,card in self.cards.items():
            review = self.reviews[cid]
            frozen = {k:v for k,v in card.items() if k!='explanation'}
            self.assertEqual(hashlib.sha256(json.dumps(frozen,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),review['sourceContentSha256'])
            self.assertEqual(hashlib.sha256(card['explanation'].encode()).hexdigest(),review['explanationSha256'])
            self.assertTrue(publication_ready(review,self.sources))
            self.assertTrue(review['hint'])
            self.assertFalse(review['authorReviewRequired'])

    def test_exactly_one_edit_of_the_requested_kind(self):
        self.assertEqual(Counter(r['lexicalEdit']['operation'] for r in self.reviews.values()),{'remove':49,'replace':18})
        for cid,review in self.reviews.items():
            edit = review['lexicalEdit']
            matches = list(re.finditer(r'(?<!\w)'+re.escape(edit['target'])+r'(?!\w)', edit['sentence'], re.I))
            self.assertEqual(len(matches),1,cid)
            match = matches[0]
            if edit['operation']=='remove':
                self.assertIn('исключив',self.cards[cid]['question'])
                self.assertEqual(edit['target'],self.cards[cid]['answer'])
                replacement = ''
            else:
                self.assertIn('заменив',self.cards[cid]['question'])
                replacement = self.cards[cid]['answer'].lower()
                self.assertEqual(edit['replacement'],replacement)
            expected = ' '.join((edit['sentence'][:match.start()]+replacement+edit['sentence'][match.end():]).split())
            expected = re.sub(r'\s+([,.;:!?])', r'\1', expected)
            self.assertEqual(expected[0].upper()+expected[1:],edit['correctedSentence'],cid)
            self.assertNotRegex(edit['correctedSentence'],r'\s+[,.;:!?]')

    def test_multiword_key_is_preserved_and_explicit(self):
        card = self.cards['B5E8E4']
        self.assertEqual(card['answer'],'большую часть')
        self.assertEqual(card['answer_verify'],'большую часть')
        self.assertIn('В ответе два слова',card['explanation'])
        self.assertIn('слово или выражение',self.cards['C3F6BC']['question'])
        self.assertTrue(self.reviews['C3F6BC']['lexicalEdit']['sentence'].startswith('Эти события'))

    def test_context_limits_and_explicit_cross_references(self):
        for cid in ['C1F6AE','D52745','7013D5','439D2C','B5E8E4']:
            self.assertEqual(self.reviews[cid]['contextAssessment'],'context_sensitive_key_preserved')
        for cid,head in [('E86C6A','орфография'),('E50C0B','предчувствие'),('C7CF0B','произвести'),('F3E10B','достичь'),('9BC9C0','вакантный')]:
            refs = self.reviews[cid]['dictionaryReview']['sourceRefs']
            self.assertIn(head,[r['headword'] for r in refs])
        refs = self.reviews['1D1FBE']['dictionaryReview']['sourceRefs']
        phrase = next(r for r in refs if r['dictionaryId']=='fipi-lexicon-2025')
        self.assertEqual(phrase['pdfPage'],11)
        self.assertEqual(phrase['role'],'phrase_form_only')


if __name__=='__main__':
    unittest.main()
