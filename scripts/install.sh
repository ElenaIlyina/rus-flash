#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/generate_manifest.py
python3 scripts/regen_cards_html.py
python3 scripts/regen_cards_html.py --check
python3 scripts/build_app_data.py
# The redesigned index is handwritten; never run the legacy sidebar generator on it.
