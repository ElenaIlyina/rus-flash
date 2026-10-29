#!/usr/bin/env python3
"""Entire task 5 bank: every highlighted form, key, group and evidence locator."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from generate_manifest import load_cards
from exam_2027 import mapping
from paronym_inventory import inventory, highlighted_words
from paronym_sources import validate_sources, validate_references


class ParonymInventoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = json.loads((ROOT / 'data/knowledge/paronym_inventory.json').read_text())
        cls.cards = load_cards()
        cls.index = inventory(cls.cards, cls.mapping, mapping)

    def test_complete_list_and_no_duplicates(self):
        self.assertEqual(self.index['cardCount'], 114)
        self.assertEqual(self.index['highlightedOccurrences'], 570)
        groups = self.index['groups']
        self.assertEqual(len(groups), 127)
        self.assertEqual(len({g['id'] for g in groups}), 127)
        self.assertEqual(groups, sorted(groups, key=lambda g: ' / '.join(g['words']).replace('ё','е')))
        self.assertEqual(sum(len(g['words']) for g in groups), 299)
        for c in self.index['cards']:
            self.assertEqual(len(c['options']), 5)
            self.assertIn(c['replacementPosition'], range(1,6))

    def test_unicode_and_real_uppercase_abbreviation(self):
        self.assertEqual(highlighted_words('<b>ВЕЧНОИ\u0306</b> мерзлоты'), ['ВЕЧНОЙ'])
        self.assertEqual(highlighted_words('в США'), ['США'])
        row = next(c for c in self.index['cards'] if c['id']=='37859F')
        self.assertEqual(row['options'][3]['form'], 'КОННОЕ')

    def test_unknown_form_is_not_silently_ignored(self):
        cards = [dict(c) for c in self.cards]
        card = next(c for c in cards if c['number']=='37859F')
        card['variants'] = list(card['variants'])
        card['variants'][0] = card['variants'][0].replace('ПРЕДОСТАВЛЯЕТ', 'НЕИЗВЕСТНОЕ')
        with self.assertRaisesRegex(ValueError, 'Unmapped paronym'):
            inventory(cards, self.mapping, mapping)

    def test_all_five_options_have_real_dictionary_evidence(self):
        book = json.loads((ROOT / 'data/knowledge/paronyms.json').read_text())
        sources = validate_sources(book, ROOT)
        audit = json.loads((ROOT / 'docs/content-audit/task-5-dictionary-coverage.json').read_text())
        by_id = {c['number']:c for c in self.cards}
        self.assertEqual(len(audit['cards']), 114)
        for row in audit['cards']:
            card = by_id[row['id']]
            frozen = {k:v for k,v in card.items() if k!='explanation'}
            self.assertEqual(hashlib.sha256(json.dumps(frozen,ensure_ascii=False,sort_keys=True).encode()).hexdigest(), row['sourceContentSha256'])
            self.assertEqual(card['answer'], row['answer'])
            self.assertEqual(card['answer_verify'], row['answerVerify'])
            self.assertEqual(len(row['options']), 5)
            for option in row['options']:
                validate_references(option['sourceRefs'], sources)


if __name__ == '__main__':
    unittest.main()
