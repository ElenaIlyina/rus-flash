#!/usr/bin/env python3
"""Offline regression checks for ambiguous classifications and audit invariants."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from generate_manifest import load_cards
from exam_2027 import mapping
from audit_verified_cards import inventory


class ContentAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards=load_cards()
        cls.by_id={c['number']:c for c in cls.cards}

    def test_positions_follow_instruction_not_just_kes(self):
        expected={'0ABFEC':2,'06A9D8':2,'012CAB':5,'060C0F':6,'011D96':24,
                  '24EAE1':24,'09169B':10,'00399F':12,'1307F2':11,
                  '03ADF2':8,'682A9C':26,'0AB17A':22,'016F80':None}
        for cid,task in expected.items():
            with self.subTest(card=cid):self.assertEqual(mapping(self.by_id[cid])['task'],task)

    def test_no_fabricated_exact_position_for_obsolete_format(self):
        old=mapping(self.by_id['016F80'])
        self.assertEqual(old['formatStatus'],'historical_format')
        self.assertIsNone(old['task'])
        self.assertEqual(mapping(self.by_id['0AB17A'])['formatStatus'],'historical_format')

    def test_inventory_retains_all_payloads(self):
        rows=inventory(self.cards)
        self.assertEqual(len(rows),935)
        self.assertEqual(len({r['id'] for r in rows}),935)
        for r in rows:
            self.assertEqual(r['answer_verify'],self.by_id[r['id']]['answer_verify'])
        conflicts=[r['id'] for r in rows if r['explanation_header_check']=='header_conflicts_with_answer']
        self.assertEqual(conflicts,['682A9C'])

    def test_official_documents_are_exactly_pinned(self):
        folder=ROOT/'docs/references/ege-2027'
        registry=json.loads((folder/'sources.json').read_text())
        for doc in registry['documents']:
            self.assertEqual(hashlib.sha256((folder/doc['file']).read_bytes()).hexdigest(),doc['sha256'])
        profile=json.loads((ROOT/'data/ege_2027_positions.json').read_text())
        self.assertEqual([p['number'] for p in profile['positions']],list(range(1,28)))
        self.assertEqual(profile['sourceStatus'],'official_fipi_draft')

    def test_review_log_matches_current_explanations(self):
        reviews=json.loads((ROOT/'docs/content-audit/explanation-reviews.json').read_text())['reviews']
        latest={}
        for review in reviews:
            if review['id'] in latest:
                self.assertEqual(review['previousExplanationSha256'], latest[review['id']]['explanationSha256'])
            latest[review['id']]=review
        for review in latest.values():
            card=self.by_id[review['id']]
            self.assertEqual(hashlib.sha256(card['explanation'].encode()).hexdigest(),review['explanationSha256'])


if __name__=='__main__':unittest.main()
