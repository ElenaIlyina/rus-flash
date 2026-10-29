"""Only server-accepted keys are published; old primary answers remain intact."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dev/scripts'))
import audit_fipi_format as formatting
import import_verified_fipi_answers as importer


class VerifiedAnswerImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cards={p.stem[5:]:json.loads(p.read_text()) for p in (ROOT/'data').glob('card_*.json')}
        cls.ledger=json.loads(importer.LEDGER.read_text());cls.raw=formatting.snapshots()

    def test_every_key_is_source_bound_and_import_is_idempotent(self):
        updates,proofs=importer.prepare(self.cards,self.ledger,self.raw)
        self.assertFalse(updates);self.assertEqual(len(proofs),2069)
        self.assertEqual(sum(bool(c['answer_verify']) for c in self.cards.values()),2069)
        self.assertEqual(sum(len(p['acceptedAnswers'])>1 for p in proofs),2)
        for proof in proofs:
            self.assertIn(proof['answerVerify'],proof['evidenceReports'])
            self.assertTrue(proof['evidenceReports'][proof['answerVerify']])
        self.assertEqual(self.cards['09C71B']['accepted_answers'],['позже','затем'])
        self.assertEqual(self.cards['432ADD']['accepted_answers'],['но','а'])
        self.assertNotIn('accepted_answers',self.cards['012CAB'])

    def test_one_missing_key_is_recovered_and_other_fields_are_not_an_import_target(self):
        cards=dict(self.cards);cards['005141']=dict(cards['005141'],answer='',answer_verify='')
        updates,_=importer.prepare(cards,self.ledger,self.raw)
        self.assertEqual(updates,{'005141':{'answer':'неизбежность','answer_verify':'неизбежность'}})
        self.assertTrue(all(set(fields)<=importer.ANSWER_FIELDS for fields in updates.values()))

    def test_unaccepted_nonempty_key_and_changed_identity_stop_the_import(self):
        for fields,message in [({'answer':'выдумано'},'Existing nonempty key'),({'guid':'0'*32},'identity/source')]:
            cards=dict(self.cards);cards['005141']=dict(cards['005141'],**fields)
            with self.assertRaisesRegex(ValueError,message):importer.prepare(cards,self.ledger,self.raw)

    def test_logged_patch_scope_and_existing_primary_answers_are_preserved(self):
        entries=[json.loads(line) for line in importer.LOG.read_text().splitlines()]
        changes=[e for e in entries if e['event']=='verified_answer_imported']
        self.assertEqual(len(changes),1290)
        self.assertEqual(sum(not e['before'].get('answer') for e in changes),1134)
        for change in changes:
            self.assertEqual(change['beforeProtectedFieldsSha256'],change['afterProtectedFieldsSha256'])
            self.assertTrue(set(change['after'])<=importer.ANSWER_FIELDS)
            if change['before'].get('answer'):
                self.assertEqual(change['before']['answer'].strip(),change['after']['answer'])


if __name__=='__main__':unittest.main()
