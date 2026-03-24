# Orionis2 Muon Analysis Repo

This repository contains the production-ready analysis package for the CosmicWatch v3X coincidence muon dataset used in the paper draft.

## Current Status
- Raw run folders normalized to sequential paper order: `0001_2026-03-01` through `0006_2026-03-22`
- Core paper figures and regression tables available in `figures/`
- Diurnal exports reduced to a compact supplement instead of a seven-figure diagnostic pack

## Main Result Snapshot
- Pressure effect: significant inverse relationship
  - `beta = 0.1294 %/hPa`, `p = 4.45e-08`
- Temperature term: not significant in the multivariable model
  - `p = 0.762`
- Diurnal 24-hour harmonic after atmospheric correction: suggestive but not significant
  - joint `p = 0.114`
  - amplitude `0.5194%` of mean

## Repo Layout
```text
cosmicwatch-muon-analysis-oshw/
├── Data/
├── figures/
├── scripts/
│   ├── acquisition/
│   │   └── maindetectorcode.py
│   └── analysis/
│       ├── analyze_muons.py
│       ├── make_figures.py
│       └── make_diurnal_figures.py
├── clean_muon_dataset.csv
├── graphbreakdown.md
└── README.md
```

- `scripts/analysis/analyze_muons.py`: builds the merged 10-minute dataset from all runs
- `scripts/analysis/make_figures.py`: generates the core paper figures, regression tables, and paper summary
- `scripts/analysis/make_diurnal_figures.py`: generates the compact supplemental diurnal check
- `scripts/acquisition/maindetectorcode.py`: Raspberry Pi logger / acquisition script
- `Data/`: normalized per-run raw folders in paper order
- `figures/`: exported figures, CSV tables, and summary text files

## Reproduce Outputs
Run from the repo root:

```bash
python3 scripts/analysis/analyze_muons.py --all-sessions
python3 scripts/analysis/make_figures.py
python3 scripts/analysis/make_diurnal_figures.py --all-sessions
```

## Most Useful Files For Writing
- `figures/paper_analysis_summary.txt`
- `figures/supplement_diurnal_summary.txt`
- `figures/session_summary.csv`
- `figures/supplement_diurnal_hourly_stats.csv`
- `graphbreakdown.md`
