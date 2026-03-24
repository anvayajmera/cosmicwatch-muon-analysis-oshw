# Graph Breakdown (Production Figure Set)

Dataset used in this package:
- Runs: 1, 2, 3, 4, 5, 6
- 10-minute bins: 2259
- UTC span: 2026-03-01 00:10 to 2026-03-23 23:20
- Mean muon rate: 13.853 counts/min

Key model results used below:
- Barometric coefficient beta = 0.1294 %/hPa (p = 4.45e-08, significant)
- Temperature term p = 0.762 (not significant)
- Diurnal joint test p = 0.114 (not significant at alpha = 0.05)
- Fitted 24h amplitude = 0.5194% of mean rate (0.0719 counts/min)

## Main Paper Figures

### 1) `figures/figure1_rate_vs_pressure.png`
What it shows: muon count rate versus atmospheric pressure, with a fitted log-linear trend.
What it means: as pressure increases, muon rate tends to decrease. This is the clearest environmental result in the dataset.
Paper-use line: pressure is the strongest environmental predictor, with beta = 0.1294 %/hPa.

### 2) `figures/figure2_rate_vs_time.png`
What it shows: raw 10-minute count rates over time for each run, plus a 3-hour moving average.
What it means: the raw series contains drift and run-to-run offsets, so visual daily patterns should not be interpreted without correction.
Paper-use line: time structure is present, but it mixes atmospheric forcing with any possible cosmic signal.

### 3) `figures/figure3_corrected_rate_vs_time.png`
What it shows: session-wise raw anomaly versus atmosphere-corrected anomaly, both smoothed over 3 hours.
What it means: atmospheric correction removes part of the slow drift and makes any residual periodic structure easier to inspect.
Paper-use line: normalization is necessary before testing for subtle diurnal modulation.

### 4) `figures/figure4_poisson_histogram.png`
What it shows: distribution of counts per 10-minute bin compared with a Poisson expectation.
What it means: counting noise is a major limitation at this count rate.
Paper-use line: statistical uncertainty remains large relative to a sub-percent diurnal signal.

### 5) `figures/figure5_diurnal_folded.png`
What it shows: atmosphere-corrected rate folded by local hour with SEM bars and a fitted 24-hour harmonic.
What it means: the shape is visually plausible, but the error bars remain comparable to or larger than the fitted amplitude.
Paper-use line: the fitted 24h signal (0.5194%) is not statistically significant (p = 0.114).

## Supplemental Diurnal Material

### 6) `figures/supplement_diurnal_by_run.png`
What it shows: run-by-run hourly folds shown as paired raw and atmosphere-corrected views.
What it means: this keeps the useful consistency check without carrying the full diagnostic pack into production.
Paper-use line: the folded pattern is not fully stable across independent runs, which is consistent with a low signal-to-noise regime.

### 7) `figures/supplement_diurnal_hourly_stats.csv`
What it contains: hourly corrected means, SEM values, and counts for each run.
What it means: this is the compact numerical companion to the supplemental diurnal figure.
Paper-use line: use this table only if the paper or appendix needs exact hourly values by run.

## Appendix Stability Figures

### 8) `figures/appendix_tilt_vs_time.png`
What it shows: detector tilt over time.
What it means: checks whether mechanical orientation drift could bias rate.
Paper-use line: use this as a detector-stability control figure.

### 9) `figures/appendix_rate_vs_tilt.png`
What it shows: count rate versus tilt.
What it means: tests whether orientation changes could create a geometric systematic.
Paper-use line: only a weak tilt-rate relation is visible, so tilt does not dominate the result.

### 10) `figures/appendix_linacc_vs_time.png`
What it shows: linear acceleration magnitude over time.
What it means: checks for motion or vibration artifacts.
Paper-use line: supports the detector-stability discussion.

### 11) `figures/appendix_mag_vs_time.png`
What it shows: magnetic field magnitude over time.
What it means: tracks magnetic-environment changes as a secondary control channel.
Paper-use line: useful as a supporting control variable, not a primary driver.

## Big Picture For The Paper

Short version:
- Pressure has a clear, statistically significant inverse relationship with muon rate.
- Temperature is not a significant predictor in this dataset.
- After atmospheric correction, the 24-hour pattern is suggestive but not statistically resolved.
- The production figure set now emphasizes the barometric result and keeps only one concise diurnal support figure.
