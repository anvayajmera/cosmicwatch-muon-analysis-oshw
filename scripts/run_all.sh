#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 scripts/core/analyze_muons.py --all-sessions
python3 scripts/core/make_figures.py
python3 scripts/core/build_station_smq_weather.py
python3 scripts/core/make_temperature_figures.py
python3 scripts/core/make_progression_and_onegraph.py
python3 scripts/core/make_literature_context.py

echo "Done. Figures: $ROOT_DIR/figures | Results: $ROOT_DIR/results"
