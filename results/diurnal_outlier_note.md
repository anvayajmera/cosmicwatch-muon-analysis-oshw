# Diurnal Progression Outlier Note

The apparent single-point spike you saw was from the old high-frequency cumulative progression table, where p-values were evaluated every 24 bins as the fit was re-estimated each time.  
That can produce occasional one-step jumps even when the overall trend is stable.

## What was changed
- `diurnal_progression_all_data.csv` is now **daily-collapsed** for a stable trend view (one checkpoint per UTC day).
- High-resolution checkpoints are still preserved in `diurnal_progression_detailed.csv`.
- The one-graph summary now plots:
  - faint high-resolution checkpoints,
  - a clean daily trend,
  - and best-so-far p-value.

## Current first significance crossings
- High-resolution crossing: `2026-03-29 08:10:00+00:00` (`p=0.04705`)
- Daily-collapsed crossing: `2026-03-29 20:10:00+00:00` (`p=0.04747`)
