# Orionis2 Muon Analysis Repo

This repo contains the AP Research analysis pipeline for CosmicWatch v3X coincidence data.

## Current Dataset Snapshot
- Runs included: 1, 38, 39, 40, 41, 42
- Total bins (10-minute): 3,415
- UTC span: 2026-03-01 00:10 to 2026-04-01 00:00

## Main Results
- Pressure effect: significant inverse relationship
  - beta = 0.1181 %/hPa, p = 1.75e-10
- Diurnal residual (after atmospheric correction): significant
  - joint p = 0.0112
  - amplitude = 0.6288% of mean rate
- Outdoor temperature term: not significant
  - multivariable p = 0.3683
- Station pressure validation (KSMQ vs BMP280)
  - MAD = 0.658 hPa, r = 0.9997

## Folder Guide
- `Data/`: raw run folders from logger
- `scripts/core/`: final production analysis scripts
- `scripts/legacy/`: optional older diagnostic scripts
- `results/`: all CSV/TXT/MD outputs from the analysis pipeline
- `figures/`: final paper figures only (PNG files)
- `assets/`: non-analysis static files

## Regenerate Final Outputs
Run from repo root:

```bash
python3 scripts/core/analyze_muons.py --all-sessions
python3 scripts/core/make_figures.py
python3 scripts/core/build_station_smq_weather.py
python3 scripts/core/make_temperature_figures.py
python3 scripts/core/make_progression_and_onegraph.py
python3 scripts/core/make_literature_context.py
```

Or run everything in one shot:

```bash
./scripts/run_all.sh
```

## Final Figure Set
1. `figures/figure1_rate_vs_pressure.png`
2. `figures/figure2_rate_vs_time.png`
3. `figures/figure3_corrected_rate_vs_time.png`
4. `figures/figure4_poisson_histogram.png`
5. `figures/figure5_diurnal_folded.png`
6. `figures/figure6_outdoor_temperature_effect.png`
7. `figures/figure_summary_one_graph.png`
