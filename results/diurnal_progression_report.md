# Diurnal Progression Report

- Dataset bins: 3415 (10-minute)
- UTC span: 2026-03-01 00:10:00+00:00 to 2026-04-01 00:00:00+00:00
- Criterion: diurnal significance at joint p(sin24, cos24) < 0.05
- `diurnal_progression_all_data.csv` is daily-collapsed (stable trend view).
- `diurnal_progression_detailed.csv` keeps high-resolution cumulative checkpoints.

## First Significant Crossing (High Resolution)

- First crossing UTC: `2026-03-29 08:10:00+00:00`
- First crossing local (EDT/EST): `2026-03-29 04:10:00-04:00`
- Bins at crossing: `3032`
- Elapsed time from start: `28.33` days
- p-value at crossing: `0.04705`
- Amplitude at crossing: `0.5547%`

## First Significant Crossing (Daily-Collapsed)

- Daily crossing UTC: `2026-03-29 20:10:00+00:00`
- Daily crossing local (EDT/EST): `2026-03-29 16:10:00-04:00`
- Bins at crossing: `3104`
- Elapsed time from start: `28.83` days
- p-value at crossing: `0.04747`
- Amplitude at crossing: `0.5463%`

## Week-by-Week Checkpoints

| Target day | Actual elapsed day | N bins | End UTC | p-value | Amp (%) |
|---:|---:|---:|---|---:|---:|
| 7 | 7.83 | 488 | 2026-03-08 20:10:00+00:00 | 0.2759 | 0.8390 |
| 14 | 14.94 | 1160 | 2026-03-15 22:40:00+00:00 | 0.413 | 0.4525 |
| 21 | 21.83 | 2096 | 2026-03-22 20:10:00+00:00 | 0.2491 | 0.4366 |
| 28 | 28.83 | 3104 | 2026-03-29 20:10:00+00:00 | 0.04747 | 0.5463 |
