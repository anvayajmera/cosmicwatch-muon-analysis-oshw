# Repo Organization

## Top-Level Structure
- `Data/`
  - Raw run folders from Raspberry Pi logger (`0001_2026-03-01`, ..., `0042_2026-03-22`).
  - Core analysis inputs per run: `cosmicwatch_coincidence.csv`, `env_60s.csv`, `system_metrics.csv`, `run_metadata.json`.
- `scripts/core/`
  - Final production pipeline scripts.
- `scripts/legacy/`
  - Optional older diagnostic scripts not used in final compact pipeline.
- `results/`
  - All non-image outputs (CSV/TXT/MD) used for writing and validation.
- `figures/`
  - Final paper figures only (`.png` files).
- `assets/`
  - Static reference assets not part of the analysis pipeline.

## Core Pipeline Scripts
- `scripts/run_all.sh`
  - One-command runner for the full core pipeline.
- `scripts/core/analyze_muons.py`
  - Ingests all runs and writes `results/clean_muon_dataset.csv` and `results/session_ingest_report.csv`.
- `scripts/core/make_figures.py`
  - Generates Figures 1–5 in `figures/` plus core model tables/summaries in `results/`.
- `scripts/core/build_station_smq_weather.py`
  - Pulls KSMQ ASOS data and writes station-aligned temperature/pressure files to `results/`.
- `scripts/core/make_temperature_figures.py`
  - Generates Figure 6 in `figures/` and temperature model summary in `results/`.
- `scripts/core/make_progression_and_onegraph.py`
  - Builds diurnal progression tables/reports in `results/` and composite Figure 7 in `figures/`.
- `scripts/core/make_literature_context.py`
  - Writes literature context summary to `results/` (optional comparison figure with `--with-figure`).

## Final Figure Files (Paper)
- `figures/figure1_rate_vs_pressure.png`
- `figures/figure2_rate_vs_time.png`
- `figures/figure3_corrected_rate_vs_time.png`
- `figures/figure4_poisson_histogram.png`
- `figures/figure5_diurnal_folded.png`
- `figures/figure6_outdoor_temperature_effect.png`
- `figures/figure_summary_one_graph.png`

## Final Results Files (Writing/Stats)
- `results/paper_analysis_summary.txt`
- `results/model_coefficients.csv`
- `results/session_summary.csv`
- `results/correlation_table.csv`
- `results/diurnal_progression_all_data.csv`
- `results/diurnal_progression_detailed.csv`
- `results/diurnal_progression_checkpoints.csv`
- `results/diurnal_progression_report.md`
- `results/station_validation_summary.txt`
- `results/external_temperature_model_summary.txt`
