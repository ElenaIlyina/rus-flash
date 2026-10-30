"""Source provenance must not confuse a bank key with an independent stress source."""
import hashlib
import html
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(name):
    return json.loads((ROOT / name).read_text())

def word(value):
    return re.sub(r'\([^)]*\)', '', html.unescape(re.sub('<[^>]+>', '', value))).strip().lower().replace('ё', 'е')

def frozen(card):
    return hashlib.sha256(json.dumps({k:v for k,v in card.items() if k!='explanation'}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

class AdditionalQuestionFormsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in read('dev/data/knowledge/ege_1_6_card_reviews.json')['cards']}

    def test_all_existing_question_forms_have_support_without_changing_their_contract(self):
        report = read('dev/docs/content-audit/additional-question-forms.json')
        self.assertEqual(report['byTask'], {'1':9, '2':48, '4':84})
        self.assertTrue(all(r['prepared'] for r in read('dev/docs/content-audit/task-1-4-readiness.json')['cards']))
        for row in report['cards']:
            with self.subTest(card=row['id']):
                c = read(f"data/card_{row['id']}.json")
                r = self.reviews[row['id']]
                self.assertEqual(frozen(c), row['sourceContentSha256'])
                self.assertEqual(hashlib.sha256(c['explanation'].encode()).hexdigest(), row['afterExplanationSha256'])
                self.assertTrue(r['hint'])
                if row['task']==2:
                    self.assertEqual([v['number'] for v in r['lexicalReview']['options'] if v['keySelects']], [int(c['answer'])])
                    self.assertEqual(len(r['lexicalReview']['options']), len(c['variants']))
                    self.assertEqual(r['lexicalReview']['numberingBasis'], 'question_fragment')
                if row['task']==4:
                    self.assertEqual(c['answer_type'], 'short')
                    wrong = [v for v in r['stressReview']['options'] if not v['correct']]
                    self.assertEqual(len(wrong), 1)
                    self.assertEqual(word(wrong[0]['sourceVariant']), word(c['answer']))

    def test_indirect_stress_evidence_is_reproducible_and_not_called_independent(self):
        count = 0
        for r in self.reviews.values():
            if r.get('stressReview', {}).get('questionForm')!='one_incorrect_stress_write_word':
                continue
            for row in r['stressReview']['options']:
                if row['evidenceType'] in {'grammatical_form_from_list', 'verified_fipi_option'}:
                    self.assertFalse(r['stressReview']['keyMatchesIndependentComparison'])
                    self.assertTrue(r['stressReview']['independentStressDictionaryPending'])
                if row['evidenceType']!='verified_fipi_option':
                    continue
                count += 1
                e = row['evidenceDetail']
                c = read(f"data/card_{e['cardId']}.json")
                self.assertEqual(c['guid'], e['guid'])
                self.assertEqual(frozen(c), e['sourceContentSha256'])
                source = c['variants'][e['part']-1]
                self.assertEqual(source, e['sourceVariant'])
                self.assertEqual(word(source), word(row['normativeForm']))
                self.assertEqual(source.strip(), row['normativeForm'])
                if 'Выпишите это слово' in c['question']:
                    self.assertNotEqual(word(source), word(c['answer']))
                else:
                    self.assertIn(str(e['part']), c['answer'])
                self.assertTrue(c['answer_verify'])
                self.assertFalse(e['independentDictionaryCheck'])
        self.assertGreater(count, 0)

    def test_comparison_words_keep_the_stress_printed_in_the_list(self):
        # Comparing paradigms must not introduce a wrong stress outside «Норма».
        accents = {}
        for group in read('data/knowledge/stress-list.json')['groups']:
            for entry in group['entries']:
                for form in re.findall('[А-ЯЁа-яё]+', entry['text']):
                    if re.search('[АЕЁИОУЫЭЮЯ]', form):
                        accented = ''.join(ch.lower()+('\u0301' if ch in 'АЕИОУЫЭЮЯ' else '') for ch in form)
                        accents.setdefault(word(form), set()).add(accented)
        for record in read('dev/docs/content-audit/additional-question-forms.json')['cards']:
            if record['task']!=4:
                continue
            text = read(f"data/card_{record['id']}.json")['explanation']
            for match in re.finditer('[а-яёА-ЯЁ\u0301]+', text):
                token = match[0].lower()
                plain = word(token.replace('\u0301', ''))
                if '\u0301' not in token or plain not in accents:
                    continue
                if text[max(0,match.start()-3):match.start()]=='не ':
                    continue  # Explicitly contrasted incorrect form, e.g. «не послала́».
                self.assertIn(token, accents[plain], (record['id'], token))

if __name__ == '__main__':
    unittest.main()
