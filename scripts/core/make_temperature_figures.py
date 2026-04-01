from __future__ import annotations

import argparse
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm


LOCAL_TZ = ZoneInfo("America/New_York")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_FILE = PROJECT_ROOT / "results" / "clean_muon_dataset.csv"
DEFAULT_STATION_FILE = PROJECT_ROOT / "results" / "station_smq_10min_temperature_pressure_comparison.csv"
DEFAULT_FIG_DIR = PROJECT_ROOT / "figures"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate meaningful outdoor-temperature findings figure.")
    parser.add_argument("--data-file", default=str(DEFAULT_DATA_FILE), help="Path to clean muon dataset CSV.")
    parser.add_argument(
        "--station-file",
        default=str(DEFAULT_STATION_FILE),
        help="Path to station-aligned temperature comparison CSV.",
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_FIG_DIR), help="Output directory for Figure 6.")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR), help="Output directory for summary text.")
    return parser.parse_args()


def load_merged(data_file: Path, station_file: Path) -> pd.DataFrame:
    data = pd.read_csv(data_file)
    station = pd.read_csv(station_file)

    data["ts_utc"] = pd.to_datetime(data["ts_utc"], utc=True, errors="coerce", format="mixed")
    station["ts_utc"] = pd.to_datetime(station["ts_utc"], utc=True, errors="coerce", format="mixed")

    data = data.dropna(subset=["ts_utc", "rate_cpm", "bmp_pressurePa_mean", "session"])
    station = station.dropna(subset=["ts_utc", "smq_tempC_interp"])

    df = data.merge(station[["ts_utc", "smq_tempC_interp"]], on="ts_utc", how="inner")
    df = df[df["rate_cpm"] > 0].copy()
    df["session"] = df["session"].astype(int)
    df = df.sort_values("ts_utc")
    return df


def fit_models(df: pd.DataFrame) -> tuple[pd.DataFrame, sm.regression.linear_model.RegressionResultsWrapper]:
    out = df.copy()
    out["log_rate"] = np.log(out["rate_cpm"])
    out["pressure_hPa"] = out["bmp_pressurePa_mean"] / 100.0
    out["dP"] = out["pressure_hPa"] - float(out["pressure_hPa"].mean())

    x = pd.DataFrame({"const": 1.0, "dP": out["dP"], "temp_out": out["smq_tempC_interp"]})
    dummies = pd.get_dummies(out["session"].astype(str), prefix="sess", drop_first=True, dtype=float)
    x = pd.concat([x, dummies], axis=1)
    model = sm.OLS(out["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 6})

    # Remove pressure + session effects so any remaining structure can be compared with outdoor temperature.
    sess_effect = np.zeros(len(out))
    for col in dummies.columns:
        sess_effect += dummies[col].values * float(model.params.get(col, 0.0))

    base = float(model.params["const"]) + float(model.params["dP"]) * out["dP"] + sess_effect
    out["anom_pct_no_pressure_session"] = 100.0 * (np.exp(out["log_rate"] - base) - 1.0)
    return out, model


def plot_temperature_findings(
    df: pd.DataFrame,
    model: sm.regression.linear_model.RegressionResultsWrapper,
    out_dir: Path,
) -> dict[str, float]:
    plt.style.use("seaborn-v0_8-whitegrid")
    # Make Figure 6 visually wider with moderate height for easier paper/web embedding.
    fig, ax = plt.subplots(1, 1, figsize=(14.0, 4.8), dpi=280, constrained_layout=True)

    # Single, simpler panel: temperature vs pressure-corrected muon anomaly.
    x = df["smq_tempC_interp"].to_numpy()
    y = df["anom_pct_no_pressure_session"].to_numpy()
    ax.scatter(x, y, s=8, alpha=0.10, color="#4c78a8", label="10-min bins (background)")

    lo = np.floor(np.nanmin(x))
    hi = np.ceil(np.nanmax(x))
    edges = np.arange(lo, hi + 2.0, 2.0)
    centers = (edges[:-1] + edges[1:]) / 2.0
    ids = np.digitize(x, edges) - 1

    bx: list[float] = []
    by: list[float] = []
    byerr: list[float] = []
    for i, c in enumerate(centers):
        yi = y[ids == i]
        yi = yi[np.isfinite(yi)]
        if len(yi) < 25:
            continue
        sem = float(np.std(yi, ddof=1) / np.sqrt(len(yi)))
        bx.append(float(c))
        by.append(float(np.mean(yi)))
        byerr.append(1.96 * sem)

    if bx:
        ax.errorbar(
            bx,
            by,
            yerr=byerr,
            fmt="o",
            color="#111111",
            capsize=3,
            linewidth=1.4,
            label="Mean +/- 95% CI",
        )

    lin = sm.OLS(y, sm.add_constant(x)).fit(cov_type="HC3")
    xline = np.linspace(np.nanmin(x), np.nanmax(x), 300)
    pred = lin.get_prediction(sm.add_constant(xline)).summary_frame(alpha=0.05)
    yline = pred["mean"].to_numpy()
    ylo = pred["mean_ci_lower"].to_numpy()
    yhi = pred["mean_ci_upper"].to_numpy()

    ax.plot(xline, yline, color="#111111", linewidth=2.2, label="Trend fit")
    ax.fill_between(xline, ylo, yhi, color="#111111", alpha=0.12, label="Trend 95% CI")
    ax.axhline(0, color="gray", linewidth=1.0, alpha=0.85)

    # Expand y-axis range slightly so point-to-point vertical separation is less visually exaggerated.
    y_stack = np.concatenate([y[np.isfinite(y)], ylo[np.isfinite(ylo)], yhi[np.isfinite(yhi)]])
    y_abs_max = float(np.nanmax(np.abs(y_stack))) if y_stack.size else 1.0
    y_lim = max(4.0, 1.40 * y_abs_max)
    ax.set_ylim(-y_lim, y_lim)

    lin_slope = float(lin.params[1])
    lin_p = float(lin.pvalues[1])
    p_temp = float(model.pvalues["temp_out"])
    corr = float(np.corrcoef(x, y)[0, 1])

    annotation = (
        f"N = {len(df)} ten-minute bins\n"
        f"Slope = {lin_slope:.4f}% per °C\n"
        f"Trend p = {lin_p:.3g}\n"
        f"Model temp-term p = {p_temp:.3g}\n"
        f"Correlation = {corr:.3f}"
    )
    ax.text(
        0.02,
        0.98,
        annotation,
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white", edgecolor="0.8", alpha=0.95),
    )

    ax.set_xlabel("Outdoor Temperature (°C), nearest station proxy")
    ax.set_ylabel("Corrected Muon Rate Change (%)")
    ax.legend(loc="upper right", fontsize=9)

    fig.suptitle("Outdoor Temperature vs Corrected Muon Rate", fontsize=13)
    fig.savefig(out_dir / "figure6_outdoor_temperature_effect.png", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out_dir / 'figure6_outdoor_temperature_effect.png'}")
    return {
        "n_bins": float(len(df)),
        "lin_slope_pct_per_C": lin_slope,
        "lin_slope_p": lin_p,
        "model_temp_p": p_temp,
        "corr_temp_vs_corranom": corr,
    }


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    results_dir = Path(args.results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)

    df = load_merged(Path(args.data_file), Path(args.station_file))
    modeled, model = fit_models(df)
    stats = plot_temperature_findings(modeled, model, out_dir)

    with open(results_dir / "external_temperature_model_summary.txt", "w", encoding="utf-8") as f:
        f.write("Outdoor Temperature Model Summary\n")
        f.write("=================================\n")
        f.write(f"N bins: {int(stats['n_bins'])}\n")
        f.write(f"Linear slope (% per C): {stats['lin_slope_pct_per_C']:.6f}\n")
        f.write(f"Linear slope p-value: {stats['lin_slope_p']:.4g}\n")
        f.write(f"Multivariable model temp p-value: {stats['model_temp_p']:.4g}\n")
        f.write(f"Correlation (temp vs corrected anomaly): {stats['corr_temp_vs_corranom']:.4f}\n")
        if stats["model_temp_p"] < 0.05:
            f.write("Interpretation: statistically significant outdoor temperature association.\n")
        else:
            f.write("Interpretation: no statistically significant outdoor temperature association.\n")
    print(f"Saved: {results_dir / 'external_temperature_model_summary.txt'}")


if __name__ == "__main__":
    main()
