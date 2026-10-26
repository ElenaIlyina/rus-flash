#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Current hash-based UI reads only catalog.json and individual card JSON files.
python3 scripts/build_app_data.py
