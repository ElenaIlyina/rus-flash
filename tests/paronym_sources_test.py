#!/usr/bin/env python3
"""Source identity, page locators, cross-reference evidence and publication guards."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from paronym_sources import validate_sources, validate_references, publication_ready


class ParonymSourcesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book=json.loads((ROOT/'data/knowledge/paronyms.json').read_text())
        cls.sources=validate_sources(cls.book,ROOT)

    def test_original_pdfs_and_publication_years(self):
        self.assertEqual(len(self.sources),4)
        first=self.sources['ruslang-paronyms-user-copy']
        second=self.sources['vishnyakova-1984-user-copy']
        self.assertEqual(first['pdfPages'],1174)
        self.assertIsNone(first['publicationYear'])
        self.assertEqual(second['publicationYear'],1984)
        self.assertEqual(second['pdfPages'],191)
        self.assertEqual(second['declaredBookPages'],352)
        third=self.sources['ozhegov-shvedova-user-copy']
        self.assertIsNone(third['publicationYear'])
        self.assertFalse(third['matchesFipiBibliographicRecord'])
        self.assertEqual(third['format'],'mobi')

    def test_bad_checksum_and_unresolved_evidence_fail(self):
        book=copy.deepcopy(self.book)
        book['sources'][0]['sha256']='0'*64
        with self.assertRaises(ValueError):validate_sources(book,ROOT)
        ref=copy.deepcopy(self.book['pairs'][0]['words'][0]['dictionaryRefs'][0])
        for change in [{'pdfPage':1175},{'pdfPage':0},{'pdfPage':True},{'dictionaryId':'unknown'},{'definitionQuote':''},{'verificationMethod':'automatic_text_search'}]:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):validate_references([{**ref,**change}],self.sources)
        self.assertFalse(publication_ready({},self.sources))
        with self.assertRaises(ValueError):publication_ready({'dictionaryReview':{'status':'verified','sourceRefs':[]}},self.sources)

    def test_electronic_article_locator_and_quote(self):
        pair=next(p for p in self.book['pairs'] if p['words'][0]['word']=='Эффективность')
        ref=pair['words'][0]['dictionaryRefs'][0]
        self.assertEqual(ref['headword'],'эффективный')
        validate_references([ref],self.sources)
        for change in [{'entryId':'missing'},{'headword':'чужое'},{'definitionQuote':'несуществующая цитата'}]:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):validate_references([{**ref,**change}],self.sources)

    def test_all_task_5_cards_have_verified_explanations(self):
        reviews=json.loads((ROOT/'data/knowledge/ege_1_6_card_reviews.json').read_text())['cards']
        task5=[r for r in reviews if r['task']==5]
        self.assertEqual(len(task5),114)
        self.assertEqual(len(self.book['pairs']),57)
        for review in task5:
            self.assertTrue(publication_ready(review,self.sources),review['id'])

    def test_lacquer_reference_is_resolved_without_overriding_exam_key(self):
        pair=self.book['pairs'][0]
        self.assertEqual([w['word'] for w in pair['words']],['Лакированный','Лакировочный','Лаковый'])
        refs=pair['words'][1]['dictionaryRefs']
        self.assertTrue(any(r['headword']=='лакировочный' and r['pdfPage']==574 for r in refs))
        self.assertTrue(any(r['headword']=='лакировальный' and r['pdfPage']==573 for r in refs))
        self.assertIn('лаковый раствор',pair['words'][2]['examples'])
        overrides=json.loads((ROOT/'data/content_review_overrides.json').read_text())['cards']
        self.assertNotIn('012CAB',overrides)
        card=json.loads((ROOT/'data/card_012CAB.json').read_text())
        self.assertEqual(card['answer'],'ЛАКИРОВОЧНЫМ')
        self.assertEqual(card['answer_verify'],'ЛАКИРОВОЧНЫМ')


if __name__=='__main__':unittest.main()
