# CosmicWatch Muon Study - Claude Packet (Current Full Dataset)

## 1) Study Objective
Determine whether atmospheric variables (especially pressure) explain muon coincidence-rate variation, and whether a statistically significant diurnal signal remains after atmospheric correction.

## 2) Data Scope Used in Current Results
- Runs included: Run 1 (2026-03-01), Run 2 (2026-03-07), Run 3 (2026-03-11), Run 4 (2026-03-19), Run 5 (2026-03-20), Run 6 (2026-03-22)
- Session IDs included: 1, 38, 39, 40, 41, 42
- Time span (UTC): 2026-03-01 00:10:00 to 2026-03-23 23:20:00
- Binning: 10-minute bins
- Total bins: 2,259

## 3) Core Quantitative Results (Use Exact Values)
- Mean coincidence rate: 13.8532 counts/min
- Pressure range: 987.41 to 1037.98 hPa
- Temperature range: 21.67 to 28.96 C

### Atmospheric model
- Barometric coefficient beta = 0.1294 %/hPa
- 95% CI = 0.0831 to 0.1758 %/hPa
- p(beta) = 4.45e-08
- Temperature term p = 0.762 (not significant)
- Model R^2 = 0.0357

### Diurnal model (after atmospheric correction)
- Joint p(sin24, cos24) = 0.114
- Harmonic amplitude = 0.0719 counts/min = 0.5194% of mean
- Peak phase = 18.46 local hour
- Single-bin Poisson 1-sigma floor (10-min) = 8.4962%
- Amplitude/floor = 0.061
- Median hourly-fold SEM = 0.8545% (max 1.0034%)

Interpretation:
- Pressure effect is significant and dominant.
- Temperature is not significant after pressure/session controls.
- 24-hour diurnal signal is not statistically resolved in this dataset.

## 4) Run-Level Notes (Barometric Fits)
- Run 1 (2026-03-01): beta = +0.1134 %/hPa, p = 0.0168
- Run 2 (2026-03-07): beta = -0.3017 %/hPa, p = 0.1389 (not significant; short/unstable run)
- Run 3 (2026-03-11): beta = +0.1632 %/hPa, p = 7.16e-09
- Run 4 (2026-03-19): beta = -1.2906 %/hPa, p = 0.0657 (short run, unstable estimate)
- Run 5 (2026-03-20): beta = -0.1749 %/hPa, p = 0.2392 (not significant)
- Run 6 (2026-03-22): beta = -0.1557 %/hPa, p = 0.3492 (not significant)

## 5) Figure Set to Use in Paper
### Main figures
1. `figures/figure1_rate_vs_pressure.png`
2. `figures/figure2_rate_vs_time.png`
3. `figures/figure3_corrected_rate_vs_time.png`
4. `figures/figure5_diurnal_folded.png`

### Extended diurnal figures (appendix or advanced results)
1. `figures/diurnal_full_01_fold_by_session.png`
2. `figures/diurnal_full_02_overall_fold_sem.png`
3. `figures/diurnal_full_03_hourly_boxplot.png`
4. `figures/diurnal_full_04_heatmaps_raw_vs_corrected.png`
5. `figures/diurnal_full_05_daily_amp_phase.png`
6. `figures/diurnal_full_06_periodogram_by_session.png`
7. `figures/diurnal_full_07_cumulative_pvalue_amp.png`

## 6) Recommended Claim Language
- Strong claim supported: "Muon coincidence rate shows a statistically significant inverse barometric dependence."
- Cautious claim required: "A diurnal-like pattern is visible after atmospheric correction, but a stable 24-hour residual signal is not statistically significant in this dataset."

## 7) Do Not Overclaim
- Do not state that a diurnal effect was detected at p < 0.05.
- State that evidence is suggestive but inconclusive for 24h harmonic in corrected residuals.

## 8) Files to Hand to a Writing Model
- `CLAUDE_PACKET.md`
- `figures/paper_analysis_summary.txt`
- `figures/diurnal_full_summary.txt`
- `graphbreakdown.md`
- `figures/session_summary.csv`
- `figures/correlation_table.csv`
- `figures/model_coefficients.csv`
- `figures/diurnal_full_daily_fits.csv`
- `figures/diurnal_full_cumulative_table.csv`
- `figures/diurnal_full_hourly_stats.csv`
