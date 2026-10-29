"""Task 7 evidence must be checked before it reaches production inputs."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import publish_content


class WordFormsPublicationTest(unittest.TestCase):
    def payload_with(self, change):
        original_read = publish_content.read

        def altered_read(path):
            value = original_read(path)
            if path == 'dev/data/knowledge/task_7_card_reviews.json':
                value = copy.deepcopy(value)
                change(value['cards'][0])
            return value

        with patch.object(publish_content, 'read', side_effect=altered_read):
            return publish_content.payloads()

    def test_fabricated_evidence_is_rejected(self):
        def change(entry):
            entry['dictionaryReview']['sourceRefs'][0]['definitionQuote'] = 'ЭТОЙ ЦИТАТЫ НЕТ В СЛОВАРЕ'
        with self.assertRaisesRegex(ValueError, 'Evidence quote'):
            self.payload_with(change)

    def test_unread_articles_do_not_publish_hint_or_sources(self):
        def change(entry):
            entry['dictionaryReview']['status'] = 'pending'
        support = self.payload_with(change)['data/knowledge/card_support.json']['cards']['09D8E7']
        self.assertFalse(support['explanationPublished'])
        self.assertEqual(support['hint'], '')
        self.assertEqual(support['dictionaryRefs'], [])


if __name__ == '__main__':
    unittest.main()
