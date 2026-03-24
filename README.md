# Orionis2 Muon Analysis Repo

This repository contains end-to-end analysis for a CosmicWatch v3X coincidence muon dataset (events + environmental + system telemetry), prepared for AP Research writing.

## Current Analysis Status
- Full-data ingest complete across 6 runs.
- All core and appendix figures regenerated.
- Atmospheric and diurnal model outputs regenerated.
- Run labels standardized (`Run N (YYYY-MM-DD)`) across exported tables.

## Main Result Snapshot
- Pressure effect: significant inverse relationship.
  - `beta = 0.1294 %/hPa`, `p = 4.45e-08`
- Temperature term: not significant in multivariable model.
  - `p = 0.762`
- Diurnal 24h harmonic after atmospheric correction: not significant at `alpha = 0.05`.
  - joint `p = 0.114`
  - amplitude `0.5194%` of mean

## Repo Layout
- `Data/`: raw per-run folders from the Raspberry Pi logger
- `analyze_muons.py`: builds merged clean 10-minute dataset
- `make_figures.py`: core figures + model tables + paper summary text
- `make_diurnal_figures.py`: extended diurnal figure pack + diagnostics
- `clean_muon_dataset.csv`: merged analysis-ready dataset
- `figures/`: generated figures, CSV tables, and summary text files
- `CLAUDE_PACKET.md`: up-to-date writing packet for paper drafting
- `graphbreakdown.md`: plain-language explanation of each graph
- `FIGURE_CAPTIONS.md`: manuscript-ready caption drafts

## Reproduce All Outputs
Run from repo root:

```bash
python3 analyze_muons.py --all-sessions
python3 make_figures.py
python3 make_diurnal_figures.py --all-sessions
```

## Most Important Files for Paper Writing
- `CLAUDE_PACKET.md`
- `figures/paper_analysis_summary.txt`
- `figures/diurnal_full_summary.txt`
- `graphbreakdown.md`
- `FIGURE_CAPTIONS.md`

