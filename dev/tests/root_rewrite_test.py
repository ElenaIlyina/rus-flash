"""Regression checks for freshly reviewed root exercises and independent stress evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('root_renderer', ROOT / 'dev/scripts/review_prefix_explanations.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

def read(path):
    return json.loads((ROOT / path).read_text())

class RootRewriteTest(unittest.TestCase):
    def test_historical_root_exercises_keep_word_answers(self):
        reviews = read('dev/data/knowledge/root_card_reviews.json')['cards']
        historical = [r for r in reviews if r.get('kind') == 'target_root_word']
        self.assertEqual(len(historical), 12)
        for review in historical:
            card = read(f'data/card_{review["id"]}.json')
            self.assertEqual(renderer.render(card, review), card['explanation'])
            self.assertTrue(card['explanation'].startswith('Ответ: ' + card['answer'] + '.'))
            self.assertEqual(len(review['rows']), 5)

    def test_complete_root_group_has_fresh_evidence_and_current_explanations(self):
        reviews = read('dev/data/knowledge/root_card_reviews.json')['cards']
        evidence = read('dev/docs/content-audit/root-dictionary-evidence.json')
        records = {r['id']: r for r in evidence['reviewedCards']}
        self.assertEqual(len(reviews), 73)
        self.assertEqual(sum(len(r['rows']) for r in reviews), 365)
        self.assertEqual(sum(len(row['words']) for r in reviews for row in r['rows']), 975)
        for review in reviews:
            card = read(f'data/card_{review["id"]}.json')
            self.assertTrue(review['rewriteReview']['previousExplanationNotTrusted'])
            self.assertEqual(renderer.render(card, review), card['explanation'])
            self.assertEqual(hashlib.sha256(card['explanation'].encode()).hexdigest(), records[review['id']]['explanationSha256'])

    def test_stressed_root_cannot_be_used_as_an_unstressed_gap_classification(self):
        review = next(r for r in read('dev/data/knowledge/root_card_reviews.json')['cards'] if r['id'] == '157C7D')
        invalid = copy.deepcopy(review)
        invalid['rows'][0]['classifications'] = ['stressed_root']
        with self.assertRaisesRegex(ValueError, 'classifications'):
            renderer.render(read('data/card_157C7D.json'), invalid)

    def test_root_target_cannot_contradict_instruction(self):
        review = next(r for r in read('dev/data/knowledge/root_card_reviews.json')['cards'] if r['id'] == '157C7D')
        invalid = copy.deepcopy(review)
        invalid['targetRoot'] = 'checked'
        with self.assertRaisesRegex(ValueError, 'Instruction'):
            renderer.render(read('data/card_157C7D.json'), invalid)

    def test_same_letter_task_cannot_be_published_as_word_answer(self):
        review = next(r for r in read('dev/data/knowledge/root_card_reviews.json')['cards'] if r['id'] == '0C24B0')
        invalid = copy.deepcopy(review)
        invalid.update(kind='target_root_word', targetRoot='checked')
        with self.assertRaises(ValueError):
            renderer.render(read('data/card_0C24B0.json'), invalid)

    def test_supplementary_stress_audit_covers_every_indirect_option(self):
        audit = read('dev/docs/content-audit/stress-dictionary-crosscheck.json')
        forms = {f['form']: f for f in audit['forms']}
        self.assertEqual(len(forms), 15)
        self.assertEqual(sum(f['status'] == 'exact_form_read' for f in forms.values()), 9)
        occurrences = {(o['cardId'], o['part']) for f in forms.values() for o in f['occurrences']}
        actual = set()
        for r in read('dev/data/knowledge/ege_1_6_card_reviews.json')['cards']:
            for option in r.get('stressReview', {}).get('options', []):
                if option['evidenceType'] not in {'grammatical_form_from_list', 'verified_fipi_option'}:
                    continue
                actual.add((r['id'], option['number']))
                self.assertEqual(option['dictionaryCrosscheck']['status'], forms[option['normativeForm']]['status'])
        self.assertEqual(actual, occurrences)

    def test_variant_or_indirect_evidence_is_not_promoted_to_exact_confirmation(self):
        forms = {f['form']: f for f in read('dev/docs/content-audit/stress-dictionary-crosscheck.json')['forms']}
        self.assertEqual(forms['откУпорил']['status'], 'indirect_paradigm_only')
        self.assertEqual(forms['исчЕрпать']['status'], 'source_disagreement_pending')
        for word in ['тОртов', 'налитА', 'добелА', 'навЕрх']:
            self.assertEqual(forms[word]['status'], 'variant_scope_pending')
        for form in forms.values():
            for evidence in form['evidence']:
                self.assertEqual(len(evidence['pageTextSha256']), 64)
                self.assertGreater(evidence['pdfPage'], 0)

if __name__ == '__main__':
    unittest.main()
