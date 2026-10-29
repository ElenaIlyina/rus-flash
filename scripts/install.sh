#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Generate the static site data from published production inputs.
python3 scripts/build_app_data.py
