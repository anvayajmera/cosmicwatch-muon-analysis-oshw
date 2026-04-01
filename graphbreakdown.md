# Graph Breakdown (Simple Final Version)

Dataset used:
- 3,415 bins (10-minute)
- UTC span: 2026-03-01 00:10 to 2026-04-01 00:00
- Sessions: 1, 38, 39, 40, 41, 42

Key results:
- Pressure beta = 0.1181 %/hPa (p = 1.75e-10)
- Diurnal joint p = 0.0112
- 24-hour amplitude = 0.6288%
- Outdoor-temperature multivariable p = 0.3683 (not significant)
- First diurnal p < 0.05 crossing: 2026-03-29 04:10 EDT (28.33 days, n = 3,032 bins)

## Final Figures to Use

### Figure 1: `figures/figure1_rate_vs_pressure.png`
Shows the inverse pressure-rate relationship.
Use this to support the barometric effect claim.

### Figure 2: `figures/figure2_rate_vs_time.png`
Shows raw rate over time.
Use this to show why correction is needed.

### Figure 3: `figures/figure3_corrected_rate_vs_time.png`
Shows raw vs corrected anomaly trends.
Use this to show the impact of atmospheric correction.

### Figure 4: `figures/figure4_poisson_histogram.png`
Shows counting-statistics behavior.
Use this to discuss uncertainty limits.

### Figure 5: `figures/figure5_diurnal_folded.png`
Shows corrected local-hour fold and harmonic fit.
Use this for the detected 24-hour residual result.

### Figure 6: `figures/figure6_outdoor_temperature_effect.png`
Shows corrected anomaly vs outdoor temperature.
Use this to support the non-significant temperature result.

### Figure 7: `figures/figure_summary_one_graph.png`
One compact overview of the full analysis.
Use this when you need one image for quick review/sharing.

## Progression File (Important)
- `results/diurnal_progression_report.md`

It tells exactly when diurnal significance first crossed p < 0.05.
