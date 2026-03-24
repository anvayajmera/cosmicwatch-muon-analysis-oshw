from __future__ import annotations

import argparse
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm


ROOT_DIR = Path(__file__).resolve().parents[2]
LOCAL_TZ = ZoneInfo("America/New_York")
OMEGA = 2.0 * np.pi / 24.0
SUPPLEMENT_FILES = {
    "supplement_diurnal_by_run.png",
    "supplement_diurnal_hourly_stats.csv",
    "supplement_diurnal_summary.txt",
}
LEGACY_DIURNAL_FILES = {
    "diurnal_full_01_fold_by_session.png",
    "diurnal_full_02_overall_fold_sem.png",
    "diurnal_full_03_hourly_boxplot.png",
    "diurnal_full_04_heatmaps_raw_vs_corrected.png",
    "diurnal_full_05_daily_amp_phase.png",
    "diurnal_full_06_periodogram_by_session.png",
    "diurnal_full_07_cumulative_pvalue_amp.png",
    "diurnal_full_cumulative_table.csv",
    "diurnal_full_daily_fits.csv",
    "diurnal_full_hourly_stats.csv",
    "diurnal_full_periodogram_peaks.csv",
    "diurnal_full_summary.txt",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a compact supplemental diurnal check.")
    parser.add_argument("--data-file", default=str(ROOT_DIR / "clean_muon_dataset.csv"), help="dataset path")
    parser.add_argument("--out-dir", default=str(ROOT_DIR / "figures"), help="output dir")
    parser.add_argument(
        "--sessions",
        nargs="+",
        type=int,
        default=None,
        help="Optional explicit session list (overrides --all-sessions).",
    )
    parser.add_argument(
        "--all-sessions",
        action="store_true",
        help="Use all sessions. Default behavior uses all sessions too.",
    )
    return parser.parse_args()


def ensure_plot_style() -> None:
    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except Exception:
        plt.style.use("ggplot")


def reset_supplemental_outputs(out_dir: Path) -> None:
    out_dir.mkdir(exist_ok=True)
    for name in SUPPLEMENT_FILES | LEGACY_DIURNAL_FILES:
        path = out_dir / name
        if path.exists():
            path.unlink()


def load_data(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    ts_col = "ts_utc" if "ts_utc" in raw.columns else raw.columns[0]
    raw[ts_col] = pd.to_datetime(raw[ts_col], utc=True, errors="coerce", format="mixed")
    df = raw.dropna(subset=[ts_col]).set_index(ts_col).sort_index()

    required = ["muon_counts", "rate_cpm", "bmp_pressurePa_mean", "bmp_tempC_mean", "session"]
    for col in required:
        if col not in df.columns:
            raise RuntimeError(f"Missing required column: {col}")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=required)
    df = df[df["rate_cpm"] > 0].copy()

    df["session"] = df["session"].astype(int)
    if "run_number" in df.columns:
        df["run_number"] = pd.to_numeric(df["run_number"], errors="coerce")
    else:
        df["run_number"] = np.nan

    if "run_date" not in df.columns:
        df["run_date"] = ""
    else:
        df["run_date"] = df["run_date"].fillna("").astype(str)

    if "run_label" not in df.columns:
        df["run_label"] = df["session"].map(lambda s: f"Session {int(s)}")
    else:
        df["run_label"] = df["run_label"].fillna("").astype(str)
        empty = df["run_label"].str.strip().eq("")
        df.loc[empty, "run_label"] = df.loc[empty, "session"].map(lambda s: f"Session {int(s)}")

    df["pressure_hPa"] = df["bmp_pressurePa_mean"] / 100.0
    df["temp_C"] = df["bmp_tempC_mean"]
    df["log_rate"] = np.log(df["rate_cpm"])

    local = df.index.tz_convert(LOCAL_TZ)
    df["local_hour"] = local.hour
    df["local_hour_float"] = local.hour + local.minute / 60.0 + local.second / 3600.0
    df["sin24"] = np.sin(OMEGA * df["local_hour_float"])
    df["cos24"] = np.cos(OMEGA * df["local_hour_float"])
    return df


def select_sessions(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    available = sorted(df["session"].unique())
    if args.sessions is not None:
        keep = set(args.sessions)
        out = df[df["session"].isin(keep)].copy()
    else:
        out = df.copy()

    if out.empty:
        raise RuntimeError(f"No rows left after session filter. Available: {available}")
    return out


def session_label_map(df: pd.DataFrame) -> dict[int, str]:
    labels: dict[int, str] = {}
    meta = (
        df[["session", "run_number", "run_label"]]
        .drop_duplicates(subset=["session"])
        .sort_values(["run_number", "session"], na_position="last")
    )
    for row in meta.itertuples(index=False):
        label = str(row.run_label).strip()
        labels[int(row.session)] = label if label else f"Session {int(row.session)}"
    return labels


def color_map_for_sessions(sessions: list[int]) -> dict[int, tuple[float, float, float, float]]:
    cmap = plt.get_cmap("tab10")
    return {s: cmap(i % 10) for i, s in enumerate(sorted(sessions))}


def fit_atmospheric_model(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    out = df.copy()
    out["dP"] = out["pressure_hPa"] - float(out["pressure_hPa"].mean())
    out["dT"] = out["temp_C"] - float(out["temp_C"].mean())

    x = out[["dP", "dT"]].copy()
    if out["session"].nunique() > 1:
        dummies = pd.get_dummies(out["session"].astype(str), prefix="sess", drop_first=True, dtype=float)
        x = pd.concat([x, dummies], axis=1)

    x = sm.add_constant(x, has_constant="add").astype(float)
    return sm.OLS(out["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 6})


def fit_diurnal_model(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    x = df[["dP", "dT", "sin24", "cos24"]].copy()
    if df["session"].nunique() > 1:
        dummies = pd.get_dummies(df["session"].astype(str), prefix="sess", drop_first=True, dtype=float)
        x = pd.concat([x, dummies], axis=1)

    x = sm.add_constant(x, has_constant="add").astype(float)
    return sm.OLS(df["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 6})


def apply_atmospheric_correction(
    df: pd.DataFrame,
    model: sm.regression.linear_model.RegressionResultsWrapper,
) -> pd.DataFrame:
    out = df.copy()
    out["dP"] = out["pressure_hPa"] - float(out["pressure_hPa"].mean())
    out["dT"] = out["temp_C"] - float(out["temp_C"].mean())
    out["rate_atm_corr"] = out["rate_cpm"] * np.exp(-(model.params["dP"] * out["dP"] + model.params["dT"] * out["dT"]))
    return out


def hourly_stats_table(df: pd.DataFrame) -> pd.DataFrame:
    hourly = (
        df.groupby(["session", "run_number", "run_label", "run_date", "local_hour"])
        .agg(
            corrected_rate_mean=("rate_atm_corr", "mean"),
            corrected_rate_std=("rate_atm_corr", "std"),
            n=("rate_atm_corr", "size"),
        )
        .reset_index()
    )
    hourly["corrected_rate_sem"] = hourly["corrected_rate_std"] / np.sqrt(hourly["n"])
    return hourly[
        [
            "session",
            "run_number",
            "run_label",
            "run_date",
            "local_hour",
            "corrected_rate_mean",
            "corrected_rate_sem",
            "n",
        ]
    ].sort_values(["run_number", "local_hour", "session"])


def plot_run_by_run_fold(
    df: pd.DataFrame,
    out_dir: Path,
    session_colors: dict[int, tuple],
    session_labels: dict[int, str],
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharex=True)

    for session in sorted(df["session"].unique()):
        sub = df[df["session"] == session]
        raw_hourly = sub.groupby("local_hour")["rate_cpm"].mean().reindex(np.arange(24))
        corr_hourly = sub.groupby("local_hour")["rate_atm_corr"].mean().reindex(np.arange(24))

        axes[0].plot(
            np.arange(24),
            raw_hourly.values,
            marker="o",
            color=session_colors[session],
            linewidth=1.8,
            label=session_labels[int(session)],
        )
        axes[1].plot(
            np.arange(24),
            corr_hourly.values,
            marker="o",
            color=session_colors[session],
            linewidth=1.8,
            label=session_labels[int(session)],
        )

    axes[0].set_title("Raw Rate Folded by Local Hour")
    axes[1].set_title("Atmosphere-corrected Rate Folded by Local Hour")
    axes[0].set_ylabel("Rate (counts/min)")
    for ax in axes:
        ax.set_xlabel("Local Hour")
        ax.set_xticks(np.arange(0, 24, 2))
        ax.legend(fontsize=9)

    fig.suptitle("Supplemental Diurnal Fold by Run", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / "supplement_diurnal_by_run.png", dpi=300)
    plt.close(fig)


def write_summary(
    df: pd.DataFrame,
    atm_model: sm.regression.linear_model.RegressionResultsWrapper,
    diurnal_model: sm.regression.linear_model.RegressionResultsWrapper,
    out_dir: Path,
) -> None:
    amp_pct = float(np.sqrt(diurnal_model.params["sin24"] ** 2 + diurnal_model.params["cos24"] ** 2) * 100.0)
    p_joint = float(diurnal_model.f_test("sin24=0, cos24=0").pvalue)
    beta_pct = float(-100.0 * atm_model.params["dP"])

    run_meta = (
        df[["run_number", "run_label"]]
        .drop_duplicates(subset=["run_number"])
        .sort_values("run_number", na_position="last")
    )
    run_labels = [str(x).strip() for x in run_meta["run_label"].tolist()]
    run_ids = [int(x) for x in run_meta["run_number"].dropna().tolist()]

    with open(out_dir / "supplement_diurnal_summary.txt", "w", encoding="utf-8") as f:
        f.write("Supplemental Diurnal Check\n")
        f.write("==========================\n")
        f.write(f"Runs: {', '.join(run_labels)}\n")
        f.write(f"Run IDs: {', '.join(str(x) for x in run_ids)}\n")
        f.write(f"UTC span: {df.index.min()} to {df.index.max()}\n")
        f.write(f"N bins: {len(df)}\n\n")
        f.write("Global atmospheric correction:\n")
        f.write(f"  beta = {beta_pct:.4f} %/hPa\n")
        f.write(f"  p(beta) = {atm_model.pvalues['dP']:.3g}\n")
        f.write(f"  p(temp) = {atm_model.pvalues['dT']:.3g}\n\n")
        f.write("Global 24h harmonic after correction:\n")
        f.write(f"  amplitude = {amp_pct:.4f} %\n")
        f.write(f"  joint p(sin24, cos24) = {p_joint:.3g}\n\n")
        f.write("Production note:\n")
        f.write("  Detailed day-by-day, spectral, heatmap, and cumulative diurnal diagnostics were removed.\n")
        f.write("  The kept supplement is limited to a run-by-run raw/corrected folded view plus the hourly summary table.\n")


def main() -> None:
    args = parse_args()
    data_file = Path(args.data_file)
    out_dir = Path(args.out_dir)

    ensure_plot_style()
    reset_supplemental_outputs(out_dir)

    df = load_data(data_file)
    df = select_sessions(df, args)
    session_labels = session_label_map(df)
    session_colors = color_map_for_sessions(sorted(df["session"].unique()))

    atm_model = fit_atmospheric_model(df)
    corr_df = apply_atmospheric_correction(df, atm_model)
    diurnal_model = fit_diurnal_model(corr_df)

    plot_run_by_run_fold(corr_df, out_dir, session_colors, session_labels)

    hourly = hourly_stats_table(corr_df)
    hourly.to_csv(out_dir / "supplement_diurnal_hourly_stats.csv", index=False)

    write_summary(corr_df, atm_model, diurnal_model, out_dir)

    print("Done.")
    print(f"Runs used: {', '.join(session_labels[int(s)] for s in sorted(corr_df['session'].unique()))}")
    print(f"Saved compact diurnal supplement to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
