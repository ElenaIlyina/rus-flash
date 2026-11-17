"""Regressions for fresh task-8 matching and primary grammar citations."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
sys.path.insert(0, str(ROOT / 'scripts'))
import review_grammar_explanations as renderer


def read(path):
    return json.loads((ROOT / path).read_text())


class GrammarReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reviews = {r['id']:r for r in read('dev/data/knowledge/grammar_card_reviews.json')['cards']}
        cls.sources = renderer.load_sources()

    def test_all_nine_sentences_and_both_keys_are_checked(self):
        support = read('data/knowledge/card_support.json')['cards']
        for cid, review in self.reviews.items():
            card = read('data/card_'+cid+'.json')
            self.assertEqual(renderer.render(card, review), card['explanation'])
            self.assertEqual(len(review['rows']), 9)
            self.assertEqual(sum(r['errorIndex'] == 0 for r in review['rows']), 4)
            self.assertEqual(support[cid]['grammarSourceRefs'], renderer.public_refs(review, self.sources))
            self.assertTrue(support[cid]['hint'])

    def test_changed_sentence_or_key_is_rejected(self):
        review = self.reviews['03ADF2']
        for field in ('sentences', 'answer', 'answer_verify'):
            card = read('data/card_03ADF2.json')
            if field == 'sentences':
                card[field][0] += ' Изменение.'
            else:
                card[field] = '12345'
            with self.assertRaises(ValueError):
                renderer.render(card, review)

    def test_duplicate_error_and_missing_control_are_rejected(self):
        card = read('data/card_03ADF2.json')
        review = copy.deepcopy(self.reviews['03ADF2'])
        review['rows'][1]['errorIndex'] = review['rows'][0]['errorIndex']
        with self.assertRaises(ValueError):
            renderer.render(card, review)

    def test_changed_evidence_and_old_explanation_reliance_are_rejected(self):
        for mutation in ('fingerprint', 'old_explanation'):
            review = copy.deepcopy(self.reviews['03ADF2'])
            if mutation == 'fingerprint':
                review['rows'][0]['grammarEvidence'][0]['textSha256'] = '0'*64
            else:
                review['rewriteReview']['oldExplanationsUsedAsEvidence'] = True
            with self.assertRaises(ValueError):
                renderer.validate_evidence(review, self.sources)

    def test_independent_matching_cannot_be_swapped_to_a_different_key(self):
        card = read('data/card_03ADF2.json')
        review = copy.deepcopy(self.reviews['03ADF2'])
        review['rows'][0]['errorIndex'], review['rows'][1]['errorIndex'] = review['rows'][1]['errorIndex'], review['rows'][0]['errorIndex']
        with self.assertRaisesRegex(ValueError, 'historical key'):
            renderer.render(card, review)

    def test_all_task8_cards_are_either_fresh_or_explicitly_pending(self):
        pending = read('dev/docs/content-audit/grammar-review-pending.json')
        pending_ids = {r['id'] for r in pending['cards']}
        ready_ids = {cid for cid, review in self.reviews.items() if not review.get('sourceReviewPending')}
        self.assertFalse(pending_ids & ready_ids)
        self.assertEqual(pending_ids, {cid for cid, review in self.reviews.items() if review.get('sourceReviewPending')})
        from exam_2027 import mapping
        cards = [json.loads(path.read_text()) for path in (ROOT / 'data').glob('card_*.json')]
        ids = {c['number'] for c in cards if mapping(c)['task'] == 8}
        self.assertEqual(ids, pending_ids | ready_ids)
        self.assertEqual(pending['unreadCards'], 0)
        self.assertEqual(pending['freshlyRewrittenCards'], len(self.reviews))

    def test_unresolved_assignment_keeps_its_warning_and_provenance(self):
        review = self.reviews['0C92F7']
        card = read('data/card_0C92F7.json')
        row = review['rows'][1]
        self.assertIsNone(row['errorIndex'])
        self.assertEqual(row['assignmentEvidence'], 'historical_key_only')
        rendered = renderer.render(card, review)
        self.assertIn('По эталону задания:', rendered)
        self.assertIn('спорное соответствие', rendered)
        support = read('data/knowledge/card_support.json')['cards']['0C92F7']
        self.assertEqual(support['explanationReviewNote'], renderer.PENDING_NOTE)
        self.assertNotIn('reviewNote', support)
        self.assertTrue(support['explanationNeedsSourceReview'])
        for change in ('flag', 'status', 'provenance'):
            altered = copy.deepcopy(review)
            if change == 'flag':
                altered['sourceReviewPending'] = False
            elif change == 'status':
                altered['status'] = 'assistant_corrected_applied'
            else:
                altered['rows'][1]['assignmentEvidence'] = 'independently_confirmed'
            with self.assertRaises(ValueError):
                renderer.render(card, altered)

    def test_resolved_perception_cases_have_source_and_no_pending_warning(self):
        support = read('data/knowledge/card_support.json')['cards']
        for cid in ('4ED72E', '8C2046'):
            review = self.reviews[cid]
            row = review['rows'][1]
            self.assertEqual(row['errorIndex'], 1)
            self.assertNotIn('historicalErrorIndex', row)
            self.assertNotIn('sourceReviewPending', review)
            self.assertIn('glazunova-2010-correlative', [e['sourceId'] for e in row['grammarEvidence']])
            renderer.validate_evidence(review, self.sources)
            self.assertNotIn('explanationReviewNote', support[cid])
            self.assertNotIn('explanationNeedsSourceReview', support[cid])
        # The distinction for ЧТО does not resolve perception with КАК.
        self.assertTrue(self.reviews['0C92F7']['sourceReviewPending'])

    def test_impersonal_infinitive_is_a_valid_control(self):
        row = self.reviews['04E391']['rows'][8]
        self.assertEqual(row['errorIndex'], 0)
        self.assertIn('инфинитиву', row['reason'])
        self.assertNotIn('correction', row)

    def test_quotation_in_indirect_speech_is_not_always_an_error(self):
        rows = self.reviews['04DFBA']['rows']
        self.assertEqual(rows[7]['errorIndex'], 4)
        self.assertEqual(rows[8]['errorIndex'], 0)
        self.assertIn('сами по себе', rows[8]['reason'])

    def test_external_citations_render_safely(self):
        script = r'''
import assert from 'node:assert/strict';
import { renderGrammarReferences as render } from './html/js/grammar-sources.js';
const url = 'https://gramota.ru/biblioteka/spravochniki/course/topic';
const valid = {part:9, url, label:'<img src=x onerror=alert(1)>'};
const result = render([valid]);
assert.ok(result.includes('Предложение 9'));
assert.ok(result.includes('rel="noopener noreferrer"'));
assert.ok(result.includes('&lt;img'));
assert.ok(!result.includes('<img'));
assert.equal(render([]), '');
assert.ok(render([valid], {kind:'style'}).includes('Источники по стилистике'));
assert.ok(render([valid], {kind:'style'}).includes('Вариант 9'));
assert.ok(!render([valid], {kind:'style'}).includes('Предложение 9'));
for (const bad of ['javascript:alert(1)', 'https://gramota.ru.evil.example/biblioteka/spravochniki/a', 'https://evil@gramota.ru/biblioteka/spravochniki/a', url+'?bad=1']) {
  assert.equal(render([{...valid,url:bad}]), '');
}
assert.equal(render([{...valid,part:10}]), '');
const ozhegov = 'https://lib.ru/DIC/OZHEGOW/ozhegow_a_d.txt';
assert.ok(render([{...valid,part:1,url:ozhegov}], {kind:'lexical'}).includes(ozhegov));
assert.equal(render([{...valid,part:1,url:ozhegov}], {kind:'grammar'}), '');
for (const bad of [ozhegov+'?bad=1', ozhegov.replace('lib.ru','lib.ru.evil.example'), ozhegov.replace('_a_d','_other')]) {
  assert.equal(render([{...valid,part:1,url:bad}], {kind:'lexical'}), '');
}
const meta = 'https://gramota.ru/meta/pech_3751.h2';
assert.ok(render([{...valid,url:meta}], {kind:'morphology'}).includes('Вариант 9'));
assert.ok(render([{...valid,url:meta}], {kind:'morphology'}).includes('Источники проверки формы слова'));
assert.equal(render([{...valid,url:meta.replace('gramota.ru','gramota.ru.evil.example')}]), '');
assert.equal(render([{...valid,url:meta+'#unsafe'}]), '');
const dictionary = 'https://gramota.ru/storage/public/normdicts/orfograficheskij_slovar.pdf#page=2619';
assert.ok(render([{...valid,url:dictionary}]).includes('#page=2619'));
for (const bad of [dictionary.replace('#page=2619','#page=0'), dictionary.replace('gramota.ru','gramota.ru.evil.example'), dictionary.replace('orfograficheskij_slovar','other')]) {
  assert.equal(render([{...valid,url:bad}]), '');
}

const journal = 'https://cyberleninka.ru/article/n/ukazatelnye-mestoimeniya-v-slozhnopodchinennyh-konstruktsiyah-so-znacheniem-peredachi-vospriyatiya-ili-osmysleniya-informatsii';
assert.ok(render([{...valid,url:journal}]).includes(journal));
for (const bad of [journal+'?x=1', journal+'/other', journal.replace('cyberleninka.ru','cyberleninka.ru.evil.example')]) {
  assert.equal(render([{...valid,url:bad}]), '');
}
const researchPdf = 'https://dcl.bas.bg/wp-content/uploads/2022/11/08_Letuchiy_STONTBgRu2022.pdf#page=24';
assert.ok(render([{...valid,url:researchPdf}]).includes('#page=24'));
assert.equal(render([{...valid,url:researchPdf.replace('#page=24','#page=25')}]), '');
const pdf = 'https://doc.fipi.ru/zhurnal-fipi/PI-2024-03.pdf#page=14';
assert.ok(render([{...valid,url:pdf}]).includes('#page=14'));
for (const bad of [pdf.replace('doc.fipi.ru','doc.fipi.ru.evil.example'), pdf.replace('#page=14','#page=0'), pdf.replace('#page=14','#javascript:alert(1)')]) {
  assert.equal(render([{...valid,url:bad}]), '');
}
'''
        subprocess.run(['node','--input-type=module','-e',script], cwd=ROOT, check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
