# Graph Breakdown (Regenerated With Full Data)

Dataset used in this regeneration:
- Sessions: 1, 38, 39, 40, 41, 42
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
What it means: as pressure increases, muon rate tends to decrease. This supports the expected barometric effect.
Paper-use line: pressure is the strongest environmental predictor in this dataset, with beta = 0.1294 %/hPa.

### 2) `figures/figure2_rate_vs_time.png`
What it shows: raw 10-minute count rates over time for each session, plus a 3-hour moving average.
What it means: raw data has visible drift and run-to-run differences, so direct visual diurnal claims from raw rate alone are risky.
Paper-use line: time-series structure exists, but it mixes atmospheric forcing and possible cosmic signal.

### 3) `figures/figure3_corrected_rate_vs_time.png`
What it shows: session-wise raw anomaly versus atmosphere-corrected anomaly (3-hour smooth).
What it means: correction removes part of the slow atmospheric trend, making residual variability easier to inspect for periodic effects.
Paper-use line: atmospheric normalization is necessary before testing for subtle diurnal modulation.

### 4) `figures/figure4_poisson_histogram.png`
What it shows: distribution of counts per 10-minute bin versus a Poisson expectation.
What it means: counting statistics are broadly consistent with Poisson-like behavior, so statistical noise is a real limitation at this rate level.
Paper-use line: random counting uncertainty remains large relative to very small expected diurnal amplitude.

### 5) `figures/figure5_diurnal_folded.png`
What it shows: atmosphere-corrected rate folded by local hour with SEM bars and a 24-hour harmonic fit.
What it means: a wave-like pattern is visually plausible, but uncertainty bars are comparable/larger than the fitted amplitude.
Paper-use line: the fitted 24h signal (0.5194%) is not statistically significant (p = 0.114).

## Extended Diurnal Pack

### 6) `figures/diurnal_full_01_fold_by_session.png`
What it shows: hourly folding for each session separately (raw and corrected).
What it means: diurnal shape is not fully stable session-to-session, suggesting low signal-to-noise and/or session-specific effects.
Paper-use line: consistency across independent sessions is limited.

### 7) `figures/diurnal_full_02_overall_fold_sem.png`
What it shows: overall corrected hourly mean with SEM, plus harmonic fit.
What it means: this is the cleanest visual summary of the global diurnal test; uncertainty still overlaps most of the fitted structure.
Paper-use line: trend is suggestive but below standard significance threshold.

### 8) `figures/diurnal_full_03_hourly_boxplot.png`
What it shows: spread of corrected rate at each local hour (boxplots).
What it means: within-hour variability is broad compared with the expected sub-percent diurnal effect.
Paper-use line: high within-hour spread weakens the ability to resolve a small periodic signal.

### 9) `figures/diurnal_full_04_heatmaps_raw_vs_corrected.png`
What it shows: date-by-hour anomaly heatmaps before and after correction.
What it means: correction removes some coherent atmospheric structure, but no strong, perfectly repeating 24h band emerges.
Paper-use line: normalization helps, but residual daily structure remains weak and variable.

### 10) `figures/diurnal_full_05_daily_amp_phase.png`
What it shows: day-by-day amplitude, phase, and significance diagnostics.
What it means: some days look stronger than others, but p-values are generally above 0.05; best day is near p = 0.0675.
Paper-use line: no single day reaches conventional significance, but several days are close and physically plausible.

### 11) `figures/diurnal_full_06_periodogram_by_session.png`
What it shows: periodogram power by session, with 24h and 12h reference lines.
What it means: sessions show different dominant periods (often 6-9h or ~22h), not a uniform sharp 24h peak across all sessions.
Paper-use line: spectral evidence for a stable 24h component is mixed.

### 12) `figures/diurnal_full_07_cumulative_pvalue_amp.png`
What it shows: as bins accumulate, diurnal p-value and amplitude estimates by session.
What it means: cumulative p-values do not cross 0.05 in this dataset (minimum cumulative p ~ 0.131).
Paper-use line: current sample size is still insufficient for a firm diurnal detection at alpha = 0.05.

## Appendix Stability Figures

### 13) `figures/appendix_tilt_vs_time.png`
What it shows: detector tilt over time.
What it means: checks whether mechanical orientation drift could bias rate.
Paper-use line: use this as a control figure for detector stability.

### 14) `figures/appendix_rate_vs_tilt.png`
What it shows: count rate versus tilt.
What it means: tests geometric sensitivity to orientation changes.
Paper-use line: any strong tilt-rate coupling would suggest non-cosmic systematics; here only weak relation is seen.

### 15) `figures/appendix_linacc_vs_time.png`
What it shows: linear acceleration magnitude over time.
What it means: checks for vibration/motion artifacts that might influence electronics or alignment.
Paper-use line: supports environmental/system stability discussion.

### 16) `figures/appendix_mag_vs_time.png`
What it shows: magnetic field magnitude over time.
What it means: tracks magnetic environment changes that could correlate with electronics behavior.
Paper-use line: useful as a secondary control variable, not a primary driver.

## How To Explain The Big Picture In Your Paper

Short version you can say:
- Pressure has a clear, statistically significant inverse relationship with muon rate.
- Temperature is not a significant predictor in this run.
- After atmospheric correction, a 24-hour pattern is visually suggestive but does not meet p < 0.05.
- So the project still validates the barometric correction pipeline and provides tentative, not definitive, diurnal evidence.
