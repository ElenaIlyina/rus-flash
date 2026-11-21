"""Source-backed target corrections retain unresolved variants and strict keys."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
from review_grammar_explanations import load_sources
from review_word_form_sources import validate


def read(path):
    return json.loads((ROOT / path).read_text())


class WordFormSourcesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = load_sources()
        cls.reviews = {r['id']:r for r in read('dev/data/knowledge/task_7_card_reviews.json')['cards']}

    def test_every_rule_application_has_a_target_source_check(self):
        expected = {cid for cid, r in self.reviews.items() if r['morphologyReview']['evidenceScope'] == 'rule_application'}
        actual = {cid for cid, r in self.reviews.items() if 'morphologySourceReview' in r}
        self.assertEqual(actual, expected)
        support = read('data/knowledge/card_support.json')['cards']
        for cid in actual:
            refs = validate(read('data/card_'+cid+'.json'), self.reviews[cid], self.sources)
            self.assertEqual(refs, support[cid]['grammarSourceRefs'])

    def test_changed_target_answer_and_fingerprint_are_rejected(self):
        original = self.reviews['09D8E7']
        card = read('data/card_09D8E7.json')
        for key in ('variantSha256', 'answer'):
            review = copy.deepcopy(original)
            review['morphologySourceReview'][key] = 'changed'
            with self.assertRaises(ValueError):
                validate(card, review, self.sources)
        review = copy.deepcopy(original)
        review['morphologySourceReview']['grammarEvidence'][0]['textSha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'evidence'):
            validate(card, review, self.sources)

    def test_neutral_plural_has_no_review_warning(self):
        support = read('data/knowledge/card_support.json')['cards']
        for cid in ('CA147A', 'F23DF9'):
            review = self.reviews[cid]
            self.assertEqual(review['morphologySourceReview']['status'], 'source_supported')
            self.assertNotIn('explanationReviewNote', support[cid])
            self.assertFalse(support[cid].get('explanationNeedsSourceReview'))
            self.assertNotIn('reviewNote', support[cid])
            self.assertTrue(support[cid]['explanationPublished'])
            changed = copy.deepcopy(review)
            changed['morphologySourceReview']['status'] = 'variant_scope_pending'
            with self.assertRaisesRegex(ValueError, 'unresolved'):
                validate(read('data/card_'+cid+'.json'), changed, self.sources)

    def test_source_check_does_not_claim_teacher_acceptance(self):
        review = copy.deepcopy(self.reviews['09D8E7'])
        review['morphologySourceReview']['independentTeacherAcceptance'] = True
        with self.assertRaisesRegex(ValueError, 'scope'):
            validate(read('data/card_09D8E7.json'), review, self.sources)


if __name__ == '__main__':
    unittest.main()
