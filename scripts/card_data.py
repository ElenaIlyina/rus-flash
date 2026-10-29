"""Shared input reading and KES parsing for the production card builder."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def extract_codes(card):
    codes = []
    for value in card.get('kes') or []:
        if 'общие' in value.lower():
            codes.append('общие')
            continue
        match = re.match(r'\s*(\d(?:\.\d)*)', value)
        if match:
            codes.append(match[1])
    return codes


def load_cards():
    return [json.loads(path.read_text()) for path in sorted((ROOT / 'data').glob('card_*.json'))
            if re.fullmatch(r'card_[0-9A-F]{6}\.json',path.name)]
