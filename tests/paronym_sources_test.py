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
        self.assertEqual(len(self.sources),2)
        first=self.sources['ruslang-paronyms-user-copy']
        second=self.sources['vishnyakova-1984-user-copy']
        self.assertEqual(first['pdfPages'],1174)
        self.assertIsNone(first['publicationYear'])
        self.assertEqual(second['publicationYear'],1984)
        self.assertEqual(second['pdfPages'],191)
        self.assertEqual(second['declaredBookPages'],352)

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

    def test_lacquer_reference_is_resolved_and_alternative_is_not_hidden(self):
        pair=self.book['pairs'][0]
        self.assertEqual([w['word'] for w in pair['words']],['Лакированный','Лакировочный','Лаковый'])
        refs=pair['words'][1]['dictionaryRefs']
        self.assertTrue(any(r['headword']=='лакировочный' and r['pdfPage']==574 for r in refs))
        self.assertTrue(any(r['headword']=='лакировальный' and r['pdfPage']==573 for r in refs))
        self.assertIn('лаковый раствор',pair['words'][2]['examples'])
        override=json.loads((ROOT/'data/content_review_overrides.json').read_text())['cards']['012CAB']
        self.assertFalse(override['eligibleForProgress'])
        card=json.loads((ROOT/'data/card_012CAB.json').read_text())
        self.assertEqual(card['answer'],'ЛАКИРОВОЧНЫМ')
        self.assertEqual(card['answer_verify'],'ЛАКИРОВОЧНЫМ')


if __name__=='__main__':unittest.main()
