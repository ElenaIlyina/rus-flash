"""Do not confuse the preposition перед with the noun перёд."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts/content'))
from extract_mobi_articles import extract


class MobiHeadwordTest(unittest.TestCase):
    SOURCE = ('<idx:entry><idx:orth value="перед"></idx:orth><div>ПЕРЕД, предлог</div></idx:entry>'
              '<idx:entry><idx:orth value="перёд"></idx:orth><div>ПЕРЁД, существительное</div></idx:entry>')

    def test_ambiguous_normalization_needs_explicit_choice(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous dictionary headword'):
            extract(self.SOURCE, {'перед'})

    def test_original_spelling_selects_the_correct_article(self):
        article, = extract(self.SOURCE, {'перед'}, {'перед': 'перед'})
        self.assertIn('предлог', article['text'])
        self.assertNotIn('существительное', article['text'])
        self.assertEqual(article['sourceHeadword'], 'перед')


if __name__ == '__main__':
    unittest.main()
