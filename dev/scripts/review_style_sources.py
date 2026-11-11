#!/usr/bin/env python3
"""Validate source-only style links without editing cards or accepting old explanations."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from exam_2027 import mapping
from review_grammar_explanations import frozen, load_sources, public_refs


def validate(card, review, sources):
    if review.get('doesNotValidateExistingExplanation') is not True or review['id'] != card['number'] or mapping(card)['task'] != 3 or frozen(card) != review['sourceContentSha256']:
        raise ValueError('Style source review does not match its immutable card')
    if len(review['rows']) != len(card['variants']):
        raise ValueError('Style option count changed')
    for number, (row, variant) in enumerate(zip(review['rows'], card['variants']), 1):
        if row['number'] != number or hashlib.sha256(variant.encode()).hexdigest() != row['variantSha256'] or not row['contextCue'].strip() or row['contextCue'] not in variant or row['scope'] != 'general_rule_criteria_only':
            raise ValueError('Style statement or evidence scope changed')
    return public_refs(review, sources)


def main():
    sources = load_sources()
    reviews = json.loads((ROOT / 'dev/data/knowledge/style_source_reviews.json').read_text())['cards']
    for review in reviews:
        card = json.loads((ROOT / 'data' / ('card_'+review['id']+'.json')).read_text())
        validate(card, review, sources)
    print(f'Style source-only reviews checked: {len(reviews)}; card text and explanations untouched')


if __name__ == '__main__':
    main()
