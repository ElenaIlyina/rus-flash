"""Source-linked punctuation reviews preserve FIPI inputs and bitmask keys."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
sys.path.insert(0, str(ROOT / 'scripts'))
import review_punctuation_explanations as renderer
from handbook_fb2 import read_handbook


class PunctuationReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = renderer.read_registry()
        cls.reviews = {r['id']:r for r in cls.registry['cards']}
        cls.external = renderer.external_sources(cls.registry)
        _, paragraphs = read_handbook(ROOT / 'data/knowledge/sources/lopatin-2007.fb2.zip')
        cls.paragraphs = {p['id']:p for p in paragraphs}

    def card(self, cid):
        return json.loads((ROOT / f'data/card_{cid}.json').read_text())

    def test_all_five_sentences_reproduce_each_published_explanation(self):
        self.assertEqual(len(self.reviews), 86)
        for cid, review in self.reviews.items():
            card = self.card(cid)
            self.assertEqual(renderer.render(card, review, self.paragraphs, self.external), card['explanation'])
            self.assertEqual(len(review['rows']), 5)
            corrected = renderer.validate(card, review, self.paragraphs, self.external)
            for original, text in zip(card['variants'], corrected):
                self.assertEqual(original.replace(',', ''), text.replace(',', ''))

    def test_fipi_allows_two_readings_but_neither_selects_web_sentence(self):
        review = self.reviews['7C9C0F']
        corrected = renderer.validate(self.card('7C9C0F'), review, self.paragraphs, self.external)
        self.assertEqual([s.count(',') for s in corrected], [0, 1, 2, 1, 1])
        self.assertIn('тогда запятых нет', review['rows'][2]['reason'])
        for row in review['rows'][1:3]:
            self.assertIn('fipi-selfprep-2023-punctuation-12', row['externalSourceIds'])

    def test_inner_enumeration_and_clause_boundary_are_all_counted(self):
        review = self.reviews['F2380D']
        texts = renderer.validate(self.card('F2380D'), review, self.paragraphs, self.external)
        self.assertEqual([s.count(',') for s in texts], [1, 1, 3, 0, 1])
        self.assertIn('мостовую, лошадиные спины, шапки извозчиков, и', texts[2])

    def test_participle_position_and_action_boundary_both_matter(self):
        review = self.reviews['D924A1']
        texts = renderer.validate(self.card('D924A1'), review, self.paragraphs, self.external)
        self.assertIn('Вронского, улыбнулась', texts[3])
        self.assertIn('весёлой, обещающей радость улыбкой', texts[3])
        review = self.reviews['DBD2F7']
        texts = renderer.validate(self.card('DBD2F7'), review, self.paragraphs, self.external)
        self.assertIn('Порыжевшая, выжженная солнцем трава', texts[1])
        self.assertEqual(texts[2].count(','), 0)

    def test_completeness_matches_all_actual_task16_cards(self):
        from exam_2027 import mapping
        task16 = set()
        for path in (ROOT / 'data').glob('card_*.json'):
            card = json.loads(path.read_text())
            if mapping(card)['task'] == 16:
                task16.add(card['number'])
        self.assertEqual(set(self.reviews), task16)

    def test_causative_infinitive_has_other_actor_and_published_source(self):
        cases = [('5ADA1A', 5, 'художники'), ('F3677E', 1, 'женщины и дети'), ('E75D9A', 3, 'другие люди')]
        for cid, part, actor in cases:
            review = self.reviews[cid]
            row = review['rows'][part - 1]
            self.assertIn(actor, row['structure'])
            self.assertIn('зависимый инфинитив', row['structure'])
            self.assertIn('https://gramota.ru/spravka/vopros/285111', [r['url'] for r in renderer.public_external_refs(review, self.external) if r['part'] == part])
        self.assertIn('была серого, бирюзового, молочного цвета', self.reviews['8E0C44']['rows'][3]['structure'])

    def test_repeated_conjunctions_and_independent_levels_differ(self):
        r = self.reviews['0366D7']
        out = renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)
        self.assertEqual([s.count(',') for s in out], [1, 1, 0, 0, 0])
        self.assertIn('таланта, ни', out[0])
        self.assertIn('театру, но и', out[1])

    def test_shared_circumstance_is_not_just_simultaneous_time(self):
        r = self.reviews['15CA45']
        self.assertEqual(renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)[1].count(','), 0)
        r = self.reviews['16C82F']
        self.assertIn('пожары, и поэтому', renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)[4])

    def test_internal_comma_in_double_conjunction_still_counts(self):
        r = self.reviews['1F6545']
        text = renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)[0]
        self.assertIn('нужное, полезное, но и', text)
        self.assertEqual(text.count(','), 2)

    def test_bitmask_is_decoded_without_changing_original_fields(self):
        review = self.reviews['0366D7']
        card = self.card('0366D7')
        self.assertEqual((card['answer'], card['answer_verify']), ('12', '11000'))
        card['answer_verify'] = '10000'
        modified = copy.deepcopy(review)
        modified['sourceContentSha256'] = renderer.frozen(card)
        with self.assertRaisesRegex(ValueError, 'Bitmask'):
            renderer.validate(card, modified, self.paragraphs, self.external)

    def test_missing_comma_or_changed_original_is_rejected(self):
        r = copy.deepcopy(self.reviews['0366D7']); r['rows'][0]['commaPositions'] = []
        with self.assertRaises(ValueError): renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)
        r = self.reviews['0366D7']; card = self.card(r['id']); card['variants'][0] += 'x'
        with self.assertRaises(ValueError): renderer.validate(card, r, self.paragraphs, self.external)

    def test_old_explanation_cannot_be_evidence(self):
        r = copy.deepcopy(self.reviews['0366D7']); r['rewriteReview']['oldExplanationsUsedAsEvidence'] = True
        with self.assertRaises(ValueError): renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)

    def test_stale_or_wrong_rule_evidence_rejected(self):
        r = copy.deepcopy(self.reviews['0366D7']); r['paragraphEvidence'][0]['textSha256'] = '0' * 64
        with self.assertRaises(ValueError): renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)
        paragraphs = copy.deepcopy(self.paragraphs)
        sid = self.reviews['0366D7']['paragraphEvidence'][0]['sourceId']; paragraphs[sid]['part'] = 'orthography'
        with self.assertRaises(ValueError): renderer.validate(self.card('0366D7'), self.reviews['0366D7'], paragraphs, self.external)

    def test_exact_commentary_links_and_reading_limits(self):
        for cid, part in [('094195', 1), ('15CA45', 3)]:
            refs = renderer.public_external_refs(self.reviews[cid], self.external)
            self.assertIn((part, renderer.BASHKIROVA_URL), [(r['part'],r['url']) for r in refs])
        bad = copy.deepcopy(self.registry); bad['externalSources'][0]['pageImageRead'] = True
        with self.assertRaises(ValueError): renderer.external_sources(bad)
        bad = copy.deepcopy(self.registry); bad['externalSources'][0]['url'] += '?unexpected=1'
        with self.assertRaises(ValueError): renderer.external_sources(bad)

    def test_published_hints_and_rule_links_cover_every_sentence(self):
        support = json.loads((ROOT / 'data/knowledge/card_support.json').read_text())['cards']
        for cid, r in self.reviews.items():
            self.assertEqual(support[cid]['hint'], r['hint'])
            self.assertEqual({ref['part'] for ref in support[cid]['ruleSourceRefs']}, {1, 2, 3, 4, 5})
            self.assertTrue(all('Пунктуация' in ref['label'] and '-punctuation-' in ref['sourceId'] for ref in support[cid]['ruleSourceRefs']))

    def test_fipi_particle_is_not_a_repeated_conjunction(self):
        r = self.reviews['556D57']
        text = renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)[2]
        self.assertIn('по лесам и полям, и закружила', text)
        self.assertNotIn('лесам,', text)
        self.assertEqual(text.count(','), 1)
        refs = renderer.public_external_refs(r, self.external)
        self.assertEqual({ref['part'] for ref in refs}, {1, 3})
        self.assertTrue(all(ref['url'].endswith('rus_yaz_2023.pdf#page=12') for ref in refs))

    def test_negative_particle_does_not_extend_subject_enumeration(self):
        r = self.reviews['57CA81']
        text = renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)[0]
        self.assertIn('Ни усталость, ни скука ни на минуту', text)
        self.assertEqual(text.count(','), 1)
        r = self.reviews['5ADA1A']
        self.assertEqual(renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)[0].count(','), 0)

    def test_three_bases_and_final_homogeneous_predicates(self):
        r = self.reviews['6AB1EC']
        text = renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)[4]
        self.assertIn('час, снег', text)
        self.assertIn('подтаивает, и', text)
        self.assertIn('веточка и закачается', text)
        self.assertEqual(text.count(','), 2)
        self.assertIn('lopatin-2007-punctuation-127', r['rows'][4]['sourceIds'])

    def test_three_alternatives_need_two_commas_without_first_or(self):
        r = self.reviews['5BCCDE']
        text = renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)[4]
        self.assertIn('отец, или друг, или брат', text)
        self.assertEqual(text.count(','), 2)

    def test_exact_room_silence_commentary_is_published(self):
        refs = renderer.public_external_refs(self.reviews['5E0203'], self.external)
        self.assertEqual([(ref['part'], ref['url']) for ref in refs], [(5, 'https://gramota.ru/spravka/vopros/332573')])

    def test_external_commentary_fingerprints_and_reading_methods_are_checked(self):
        r = copy.deepcopy(self.reviews['556D57'])
        r['rows'][2]['externalSourceEvidence'][0]['excerptSha256'] = '0' * 64
        with self.assertRaises(ValueError):
            renderer.validate(self.card(r['id']), r, self.paragraphs, self.external)
        bad = copy.deepcopy(self.registry)
        next(s for s in bad['externalSources'] if s['id'] == 'fipi-selfprep-2023-punctuation-12').pop('fileSha256')
        with self.assertRaises(ValueError):
            renderer.external_sources(bad)
