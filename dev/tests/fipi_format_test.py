"""Source-backed presentation repairs preserve identity, answers and shared passages."""
import json
from pathlib import Path
import sys
import unittest

from lxml import html

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dev/scripts'))
import audit_fipi_format as audit


class FipiFormatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=audit.snapshots()
        cls.cards={p.stem[5:]:json.loads(p.read_text()) for p in (ROOT/'data').glob('card_*.json')}

    def test_every_question_and_list_matches_source_or_has_explicit_damage_exception(self):
        damaged=[]
        for cid,card in self.cards.items():
            with self.subTest(card=cid):
                proposed,changes,issues=audit.inspect(card,self.raw[cid])
                self.assertFalse(changes)
                if issues:damaged.append(cid)
                for key in proposed:
                    if any(i['field']==key for i in issues):continue
                    values=card[key] if isinstance(card[key],list) else [card[key]]
                    for value in values:
                        tree=html.fragment_fromstring(value,create_parent='div')
                        for node in tree.iterdescendants():
                            self.assertIn(node.tag,audit.KEEP|{'br'})
                            self.assertFalse(node.attrib)
        self.assertEqual(sorted(damaged),['044054','139F0C','39AA6F','7755A0','802933','BF989E','C96DCA','F8BFF9'])

    def test_known_extraction_failures_are_restored_without_moving_options(self):
        for cid in ['2D813D','AC9F9C','B7E06E','C0A0ED','0585E4','14AF4C']:
            self.assertEqual(len(self.cards[cid]['variants']),5)
            self.assertTrue(all(audit.visible(v) for v in self.cards[cid]['variants']))
        self.assertEqual(self.cards['279C1A']['variants'],[
            'симв..лизировать, дек..рация, отн..шение',
            'д..лина, к..ртонная (коробка), предпол..гать',
            'пров..нциальный, прис..гать (Родине), раст..рать',
            'с..мфония, перем..ститься, интелл..ктуальный',
            'сокр..щать, зак..зать, осч..стливить'])
        self.assertNotIn('симв..',self.cards['279C1A']['question'])
        self.assertTrue(self.cards['1CB807']['variants'][3].endswith('и сделала в ней пометку.'))
        self.assertEqual(len(self.cards['1CB807']['variants']),5)
        self.assertTrue(self.cards['E0107D']['variants'][4].endswith('(В)ПЕРВЫЕ.'))
        self.assertEqual(self.cards['DE0170']['variants'][2:4],['брАла','(лиса) ловкА'])

    def test_meaningful_markup_and_matching_columns_are_retained(self):
        self.assertIn('<b>ПЕЧАТАТЬ.</b>',self.cards['082CB8']['variants'][0])
        self.assertIn('<i>П. доклад на машинке.',self.cards['082CB8']['variants'][0])
        c=self.cards['03ADF2']
        self.assertEqual(len(c['errors']),5)
        self.assertEqual(len(c['sentences']),9)
        self.assertNotIn(c['sentences'][0],c['question'])
        self.assertIn('Запишите в таблицу',c['question'])
        self.assertIn('Вчера дождь лил',c['sentences'][0])

    def test_change_log_proves_nonpresentation_fields_are_unchanged(self):
        entries=[json.loads(line) for line in audit.LOG.read_text().splitlines()]
        patches=[e for e in entries if e['event']=='raw_format_restored']
        self.assertEqual(len(patches),1722)
        for patch in patches:
            self.assertTrue(set(patch['fields'])<=set(audit.FIELDS))
            card=self.cards[patch['cardId']]
            self.assertEqual(patch['beforeNonPresentationSha256'],patch['afterNonPresentationSha256'])
            self.assertEqual(patch['rawSourceContentSha256'],audit.digest(self.raw[patch['cardId']]))

    def test_raw_html_is_not_an_execution_or_attribute_source(self):
        node=html.fragment_fromstring('<p onclick="bad()">Слово <b class="x">важно</b><script>bad()</script><img src="bad" onerror="bad()"><span> &lt;…&gt;</span></p>')
        self.assertEqual(audit.clean(node),'Слово <b>важно</b> &lt;…&gt;')


if __name__=='__main__':unittest.main()
