# CosmicWatch Muon Study - Writing Packet (Updated Run 42 Included)

## 1) Study Objective
Determine whether atmospheric variables (especially pressure) explain coincidence muon-rate variation, and whether a statistically significant 24-hour pattern remains after atmospheric correction.

## 2) Data Scope
- Runs: Run 1 (2026-03-01), Run 2 (2026-03-07), Run 3 (2026-03-11), Run 4 (2026-03-19), Run 5 (2026-03-20), Run 6 (2026-03-22)
- Session IDs: 1, 38, 39, 40, 41, 42
- Binning: 10-minute
- Total bins: 3,415
- UTC span: 2026-03-01 00:10:00 to 2026-04-01 00:00:00

## 3) Core Results (Use Exact Values)
- Mean coincidence rate: 13.7757 counts/min
- Pressure range: 987.41 to 1037.98 hPa
- Temperature range: 21.67 to 29.96 C

### Atmospheric model
- Barometric coefficient beta = 0.1181 %/hPa
- 95% CI = 0.0818 to 0.1544 %/hPa
- p(beta) = 1.75e-10
- Temperature term p = 0.499 (not significant)
- Model R^2 = 0.0300

### Diurnal model (after atmospheric correction)
- Joint p(sin24, cos24) = 0.0112
- Harmonic amplitude = 0.0866 counts/min = 0.6288% of mean
- Peak phase = 19.33 local hour
- Single-bin Poisson 1-sigma floor (10-min) = 8.5201%
- Amplitude/floor = 0.074
- Median hourly-fold SEM = 0.7046% (max 0.8154%)

Interpretation:
- Pressure effect is strong and significant.
- Temperature is not significant after pressure/session control.
- A 24-hour residual modulation is statistically detected, with small effect size.

## 4) Progression Timeline (When Significance Happened)
Source file: `results/diurnal_progression_report.md`
Progression table for stable trend view: `results/diurnal_progression_all_data.csv` (daily-collapsed)
High-resolution progression table: `results/diurnal_progression_detailed.csv`

- First crossing of p < 0.05:
  - UTC: 2026-03-29 08:10:00
  - Local (EDT): 2026-03-29 04:10:00
  - At 3,032 bins
  - 28.33 days from start
  - p = 0.04705

Week-style checkpoints:
- ~7 days: p = 0.3457
- ~14 days: p = 0.2779
- ~21 days: p = 0.3183
- ~28 days: p = 0.08481

## 5) Outdoor Station Validation (KSMQ vs BMP280)
Source file: `results/station_validation_summary.txt`

- Pressure MAD: 0.658 hPa
- Pressure correlation: 0.9997
- Temperature MAD: 18.825 C (indoor/outdoor offset expected)

Outdoor-temperature effect on corrected rate:
- Linear p = 0.1686
- Multivariable p = 0.3683
- Conclusion: not statistically significant.

## 6) Final Figure Set (Use These)
1. `figures/figure1_rate_vs_pressure.png`
2. `figures/figure2_rate_vs_time.png`
3. `figures/figure3_corrected_rate_vs_time.png`
4. `figures/figure4_poisson_histogram.png`
5. `figures/figure5_diurnal_folded.png`
6. `figures/figure6_outdoor_temperature_effect.png`
7. `figures/figure_summary_one_graph.png` (single all-in-one summary for quick sharing/upload)

## 7) Recommended Claim Language
- Strong claim: "Coincidence muon rate shows a significant inverse barometric dependence."
- Careful claim: "After atmospheric correction, a statistically significant but small 24-hour residual modulation is detected."

## 8) Files to Hand to a Writing Model
- `CLAUDE_PACKET.md`
- `graphbreakdown.md`
- `FIGURE_CAPTIONS.md`
- `results/paper_analysis_summary.txt`
- `results/diurnal_progression_report.md`
- `results/diurnal_progression_checkpoints.csv`
- `results/external_temperature_model_summary.txt`
- `results/station_validation_summary.txt`
- `results/session_summary.csv`
- `results/model_coefficients.csv`
