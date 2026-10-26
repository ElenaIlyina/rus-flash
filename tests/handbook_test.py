#!/usr/bin/env python3
"""Edition provenance, structural completeness, safe FB2 import, exact rule references."""
import hashlib
from unittest.mock import patch
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from handbook_fb2 import read_handbook, apply_errata
from review_prefix_explanations import render as render_prefix
import review_prefix_explanations as prefix_tool


class HandbookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=json.loads((ROOT/'data/knowledge/source_registry.json').read_text())['editions'][0]
        cls.meta,cls.paragraphs=read_handbook(ROOT/'data/knowledge'/cls.registry['sourceFile'])
        cls.by_id={p['id']:p for p in cls.paragraphs}

    def test_edition_not_mislabeled_as_2020(self):
        self.assertEqual(self.meta['year'],'2007')
        self.assertEqual(self.meta['publisher'],'Эксмо')
        self.assertEqual(self.meta['isbn'],'978-5-699-18553-5')
        self.assertFalse(self.meta['matchesFipi2020Edition'])
        for key in ['archiveSha256','fb2Sha256']:
            self.assertEqual(self.meta[key],self.registry[key])

    def test_numbering_is_scoped_and_complete(self):
        self.assertEqual(len(self.by_id),386)
        for part,count in [('orthography',219),('punctuation',167)]:
            self.assertEqual([p['number'] for p in self.paragraphs if p['part']==part],list(range(1,count+1)))
        self.assertNotEqual(self.by_id['lopatin-2007-orthography-11']['body'],self.by_id['lopatin-2007-punctuation-11']['body'])
        self.assertNotIn('Гласные после шипящих',self.by_id['lopatin-2007-orthography-12']['body'])

    def test_first_rules_have_real_source_paragraphs(self):
        rules=json.loads((ROOT/'data/knowledge/handbook.json').read_text())['paragraphs']
        for rule in rules:
            self.assertTrue(rule['sourceRefs'])
            for ref in rule['sourceRefs']:
                p=self.by_id[ref['sourceId']]
                self.assertEqual(p['number'],ref['paragraph'])
                self.assertEqual(p['part'],ref['part'])
                self.assertIsNone(ref['printedPage'])
        self.assertIn('безвкусный',self.by_id['lopatin-2007-orthography-82']['body'])
        self.assertIn('сверх-',self.by_id['lopatin-2007-orthography-11']['body'])
        self.assertIn('приставок',self.by_id['lopatin-2007-orthography-12']['body'])

    def test_errata_preserve_original_and_do_not_guess(self):
        _, paragraphs=read_handbook(ROOT/'data/knowledge'/self.registry['sourceFile'])
        before={p['id']:p['body'] for p in paragraphs}
        entries=json.loads((ROOT/'data/knowledge'/self.registry['errataFile']).read_text())['entries']
        apply_errata(paragraphs,entries)
        after={p['id']:p for p in paragraphs}
        self.assertIn('трёхимпулъсный',before['lopatin-2007-orthography-11'])
        self.assertIn('трёхимпульсный',after['lopatin-2007-orthography-11']['body'])
        self.assertIn('sourceTextSha256',after['lopatin-2007-orthography-11'])
        self.assertEqual(before['lopatin-2007-orthography-12'],after['lopatin-2007-orthography-12']['body'])

    def test_prefix_explanations_match_rows_and_historical_answers(self):
        reviews=json.loads((ROOT/'data/knowledge/prefix_card_reviews.json').read_text())['cards']
        self.assertEqual(len(reviews),12)
        for review in reviews:
            card=json.loads((ROOT/'data'/f"card_{review['id']}.json").read_text())
            self.assertEqual(render_prefix(card,review),card['explanation'])
            for row in review['rows']:
                for sid in row['sourceIds']:self.assertIn(sid,self.by_id)

    def test_prefix_batch_checks_every_card_before_writing(self):
        reviews=json.loads((ROOT/'data/knowledge/prefix_card_reviews.json').read_text())['cards'][:2]
        reviews=copy.deepcopy(reviews)
        reviews[1]['rows'][0]['words'][0]='ошибка'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'data/knowledge').mkdir(parents=True)
            (root/'docs/content-audit').mkdir(parents=True)
            for review in reviews:
                card=json.loads((ROOT/'data'/f"card_{review['id']}.json").read_text())
                card['explanation']='before'
                (root/'data'/f"card_{review['id']}.json").write_text(json.dumps(card))
            (root/'data/knowledge/prefix_card_reviews.json').write_text(json.dumps({'cards':reviews}))
            (root/'docs/content-audit/explanation-reviews.json').write_text('{"reviews":[]}')
            before={p:p.read_bytes() for p in root.rglob('*.json')}
            with patch.object(prefix_tool,'ROOT',root),patch.object(sys,'argv',['review_prefix_explanations.py','--write']):
                with self.assertRaises(ValueError):prefix_tool.main()
            self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*.json')})

    def test_active_xml_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'bad.zip'
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('a.fb2','<!DOCTYPE foo [<!ENTITY x "abc">]><root/>')
            with self.assertRaises(ValueError):read_handbook(path)
            with zipfile.ZipFile(path,'w') as z:
                z.writestr('a.fb2','<root/>');z.writestr('b.fb2','<root/>')
            with self.assertRaises(ValueError):read_handbook(path)

    def test_uploaded_pdf_is_a_separate_edition_and_page_system(self):
        folder=ROOT/'docs/references/lopatin-2009'
        reg=json.loads((folder/'sources.json').read_text())
        self.assertEqual(hashlib.sha256((folder/reg['file']).read_bytes()).hexdigest(),reg['sha256'])
        self.assertEqual(reg['declaredYear'],2009)
        self.assertNotEqual(reg['declaredBookPages'],reg['actualPdfPages'])
        locators=json.loads((folder/'paragraph-locators.json').read_text())
        self.assertEqual(locators['locatorType'],'pdf_page_not_printed_page')
        rows=locators['paragraphs']
        self.assertEqual(len({(r['part'],r['paragraph']) for r in rows}),386)
        self.assertEqual(next(r['pdfPage'] for r in rows if r['part']=='orthography' and r['paragraph']==12),25)

    def test_navigator_pdfs_are_pinned(self):
        folder=ROOT/'docs/references/fipi-navigator-2026'
        registry=json.loads((folder/'sources.json').read_text())
        for doc in registry['documents']:
            self.assertEqual(doc['year'],2026)
            self.assertEqual(hashlib.sha256((folder/doc['localFile']).read_bytes()).hexdigest(),doc['sha256'])


if __name__=='__main__':unittest.main()
