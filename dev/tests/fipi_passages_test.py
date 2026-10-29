"""Full-page group bindings, source highlights and formatting-only text repair."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dev/scripts'))
import audit_fipi_passages as passages
import audit_fipi_format as presentation


class FipiPassagesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards={p.stem[5:]:json.loads(p.read_text()) for p in (ROOT/'data').glob('card_*.json')}
        cls.data=passages.SOURCE.read_bytes()
        cls.groups,cls.rows,cls.decoded=passages.parse_page(cls.data,cls.cards)

    def test_original_encoding_and_every_explicit_group_are_verified(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(),passages.SOURCE_SHA256)
        self.assertEqual(self.decoded.encode('cp1251'),self.data)
        self.assertEqual(len(self.rows),2140)  # Includes all 71 qblock1 essays.
        self.assertEqual(len(self.groups),159)
        members=[m['cardId'] for g in self.groups for m in g['cards']]
        self.assertEqual(len(members),655)
        self.assertEqual(len(set(members)),655)
        self.assertEqual(set(members),{cid for cid,c in self.cards.items() if c.get('text')})
        for group in self.groups:
            for index,member in enumerate(group['cards'],1):
                cid=member['cardId']
                self.assertEqual(member['numberInGroup'],index)
                self.assertEqual(self.rows[cid]['groupId'],group['groupId'])
                self.assertEqual(self.cards[cid]['text'],group['text'])
                self.assertNotIn('\ufffd',group['text'])

    def test_previously_approved_missing_highlights_are_present_in_the_full_source(self):
        expected={'082CB8':['потеряла'],'2BA3EC':['масса','наследный','инкогнито'],
                  '9273A5':['храм'],'F5E433':['стиль','опыта'],'E96B4A':['оценивать','ход']}
        for cid,words in expected.items():
            tree=presentation.html.fragment_fromstring(self.cards[cid]['text'],create_parent='div')
            highlights=tree.xpath('.//b/u/text()')
            for word in words:self.assertIn(word,highlights,cid)
        self.assertEqual(self.rows['6E2A0F']['groupId'],'03EEC3')
        self.assertEqual(self.rows['8CD68D']['groupId'],'7A71AB')

    def test_log_preserves_every_other_field_and_old_word_content(self):
        entries=[json.loads(line) for line in passages.LOG.read_text().splitlines()]
        patches=[e for e in entries if e['event']=='shared_passage_format_restored']
        self.assertEqual(len(patches),547)
        for patch in patches:
            self.assertEqual(patch['beforeProtectedFieldsSha256'],patch['afterProtectedFieldsSha256'])
            self.assertEqual(presentation.visible(patch['before']),presentation.visible(patch['after']))
            self.assertEqual(patch['after'],self.cards[patch['cardId']]['text'])
            self.assertEqual(patch['sourcePageSha256'],passages.SOURCE_SHA256)

    def test_mismatched_identity_group_and_encoding_stop_the_import(self):
        cases=[(self.data.replace(b'004579B3C47B9B3149EEA1091929EEBB',b'00000000000000000000000000000000',1),'GUID mismatch'),
               (self.data.replace(b'1 (BA7D49)',b'1 (000000)',1),'group mismatch'),
               (self.data.replace(b'charset=windows-1251',b'charset=utf-8',1),'Windows-1251')]
        for damaged,message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError,message):passages.parse_page(damaged,self.cards)


if __name__=='__main__':unittest.main()
