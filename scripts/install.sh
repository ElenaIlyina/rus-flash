#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/generate_manifest.py
python3 scripts/regen_cards_html.py
python3 scripts/regen_cards_html.py --check
python3 scripts/build_app_data.py
python3 scripts/build_app_pages.py
# Edit scripts/templates/app.html for the shared shell, not generated pages.
