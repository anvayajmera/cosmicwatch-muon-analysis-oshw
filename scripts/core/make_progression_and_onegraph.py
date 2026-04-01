from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = PROJECT_ROOT / "results" / "clean_muon_dataset.csv"
FIG_DIR = PROJECT_ROOT / "figures"
RESULTS_DIR = PROJECT_ROOT / "results"
LOCAL_TZ = ZoneInfo("America/New_York")
OMEGA = 2.0 * np.pi / 24.0


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_FILE)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True, errors="coerce", format="mixed")
    req = ["ts_utc", "rate_cpm", "bmp_pressurePa_mean", "bmp_tempC_mean", "session"]
    df = df.dropna(subset=req).copy()
    df = df[df["rate_cpm"] > 0].copy()
    df = df.sort_values("ts_utc").set_index("ts_utc")
    df["session"] = df["session"].astype(int)
    df["pressure_hPa"] = df["bmp_pressurePa_mean"] / 100.0
    df["temp_C"] = df["bmp_tempC_mean"]
    df["log_rate"] = np.log(df["rate_cpm"])
    df["dP"] = df["pressure_hPa"] - df["pressure_hPa"].mean()
    df["dT"] = df["temp_C"] - df["temp_C"].mean()
    local = df.index.tz_convert(LOCAL_TZ)
    df["local_hour_float"] = local.hour + local.minute / 60.0 + local.second / 3600.0
    df["sin24"] = np.sin(OMEGA * df["local_hour_float"])
    df["cos24"] = np.cos(OMEGA * df["local_hour_float"])
    return df


def fit_atmospheric(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    x = df[["dP", "dT"]].copy()
    dummies = pd.get_dummies(df["session"].astype(str), prefix="sess", drop_first=True, dtype=float)
    x = pd.concat([x, dummies], axis=1)
    x = sm.add_constant(x, has_constant="add").astype(float)
    return sm.OLS(df["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 6})


def fit_diurnal(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    x = df[["dP", "dT", "sin24", "cos24"]].copy()
    dummies = pd.get_dummies(df["session"].astype(str), prefix="sess", drop_first=True, dtype=float)
    x = pd.concat([x, dummies], axis=1)
    x = sm.add_constant(x, has_constant="add").astype(float)
    return sm.OLS(df["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 6})


def corrected_series(df: pd.DataFrame, atm_model: sm.regression.linear_model.RegressionResultsWrapper) -> pd.DataFrame:
    out = df.copy()
    out["rate_atm_corr"] = out["rate_cpm"] * np.exp(
        -(atm_model.params["dP"] * out["dP"] + atm_model.params["dT"] * out["dT"])
    )
    out["corr_anom_pct"] = 100.0 * (out["rate_atm_corr"] / out["rate_atm_corr"].mean() - 1.0)
    return out


def cumulative_progression(df: pd.DataFrame, min_n: int = 200, step: int = 24) -> pd.DataFrame:
    rows: list[dict] = []
    start_ts = df.index.min()

    n_values = list(range(min_n, len(df) + 1, step))
    if not n_values:
        n_values = [len(df)]
    elif n_values[-1] != len(df):
        n_values.append(len(df))

    for n in n_values:
        sub = df.iloc[:n]
        x = sub[["dP", "dT", "sin24", "cos24"]].copy()
        dummies = pd.get_dummies(sub["session"].astype(str), prefix="sess", drop_first=True, dtype=float)
        x = pd.concat([x, dummies], axis=1)
        x = sm.add_constant(x, has_constant="add").astype(float)
        m = sm.OLS(sub["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 6})

        p_joint = float(m.f_test("sin24=0, cos24=0").pvalue)
        amp_pct = float(np.sqrt(m.params["sin24"] ** 2 + m.params["cos24"] ** 2) * 100.0)
        end_ts = sub.index[-1]
        rows.append(
            {
                "n_bins": int(n),
                "end_ts_utc": end_ts,
                "elapsed_days": float((end_ts - start_ts).total_seconds() / 86400.0),
                "joint_p_value": p_joint,
                "amp_pct": amp_pct,
            }
        )
    return pd.DataFrame(rows)


def collapse_progression_to_daily(prog_detail: pd.DataFrame) -> pd.DataFrame:
    p = prog_detail.copy()
    p["end_ts_utc"] = pd.to_datetime(p["end_ts_utc"], utc=True, errors="coerce", format="mixed")
    p = p.dropna(subset=["end_ts_utc"]).sort_values("end_ts_utc")
    p["utc_day"] = p["end_ts_utc"].dt.floor("D")

    daily = p.groupby("utc_day", as_index=False).tail(1).copy()
    daily = daily.sort_values("end_ts_utc")
    return daily[["n_bins", "end_ts_utc", "elapsed_days", "joint_p_value", "amp_pct"]].reset_index(drop=True)


def weekly_checkpoints(prog: pd.DataFrame, targets_days: list[int]) -> pd.DataFrame:
    rows: list[dict] = []
    for d in targets_days:
        cand = prog[prog["elapsed_days"] >= d]
        row = prog.iloc[-1] if cand.empty else cand.iloc[0]
        rows.append(
            {
                "target_days": d,
                "actual_elapsed_days": float(row["elapsed_days"]),
                "n_bins": int(row["n_bins"]),
                "end_ts_utc": row["end_ts_utc"],
                "joint_p_value": float(row["joint_p_value"]),
                "amp_pct": float(row["amp_pct"]),
            }
        )
    return pd.DataFrame(rows)


def first_significant_row(prog: pd.DataFrame) -> pd.Series | None:
    sub = prog[prog["joint_p_value"] < 0.05]
    if sub.empty:
        return None
    return sub.iloc[0]


def write_report(df: pd.DataFrame, prog_detail: pd.DataFrame, prog_daily: pd.DataFrame, wk: pd.DataFrame) -> None:
    first_sig_detail = first_significant_row(prog_detail)
    first_sig_daily = first_significant_row(prog_daily)

    out = RESULTS_DIR / "diurnal_progression_report.md"
    with out.open("w", encoding="utf-8") as f:
        f.write("# Diurnal Progression Report\n\n")
        f.write(f"- Dataset bins: {len(df)} (10-minute)\n")
        f.write(f"- UTC span: {df.index.min()} to {df.index.max()}\n")
        f.write("- Criterion: diurnal significance at joint p(sin24, cos24) < 0.05\n")
        f.write("- `diurnal_progression_all_data.csv` is daily-collapsed (stable trend view).\n")
        f.write("- `diurnal_progression_detailed.csv` keeps high-resolution cumulative checkpoints.\n\n")

        f.write("## First Significant Crossing (High Resolution)\n\n")
        if first_sig_detail is not None:
            ts_utc = pd.to_datetime(first_sig_detail["end_ts_utc"], utc=True)
            ts_local = ts_utc.tz_convert(LOCAL_TZ)
            f.write(f"- First crossing UTC: `{ts_utc}`\n")
            f.write(f"- First crossing local (EDT/EST): `{ts_local}`\n")
            f.write(f"- Bins at crossing: `{int(first_sig_detail['n_bins'])}`\n")
            f.write(f"- Elapsed time from start: `{first_sig_detail['elapsed_days']:.2f}` days\n")
            f.write(f"- p-value at crossing: `{first_sig_detail['joint_p_value']:.4g}`\n")
            f.write(f"- Amplitude at crossing: `{first_sig_detail['amp_pct']:.4f}%`\n\n")
        else:
            f.write("- No crossing below p < 0.05 in high-resolution progression.\n\n")

        f.write("## First Significant Crossing (Daily-Collapsed)\n\n")
        if first_sig_daily is not None:
            ts_utc = pd.to_datetime(first_sig_daily["end_ts_utc"], utc=True)
            ts_local = ts_utc.tz_convert(LOCAL_TZ)
            f.write(f"- Daily crossing UTC: `{ts_utc}`\n")
            f.write(f"- Daily crossing local (EDT/EST): `{ts_local}`\n")
            f.write(f"- Bins at crossing: `{int(first_sig_daily['n_bins'])}`\n")
            f.write(f"- Elapsed time from start: `{first_sig_daily['elapsed_days']:.2f}` days\n")
            f.write(f"- p-value at crossing: `{first_sig_daily['joint_p_value']:.4g}`\n")
            f.write(f"- Amplitude at crossing: `{first_sig_daily['amp_pct']:.4f}%`\n\n")
        else:
            f.write("- No crossing below p < 0.05 in daily-collapsed progression.\n\n")

        f.write("## Week-by-Week Checkpoints\n\n")
        f.write("| Target day | Actual elapsed day | N bins | End UTC | p-value | Amp (%) |\n")
        f.write("|---:|---:|---:|---|---:|---:|\n")
        for _, r in wk.iterrows():
            f.write(
                f"| {int(r['target_days'])} | {r['actual_elapsed_days']:.2f} | {int(r['n_bins'])} | "
                f"{pd.to_datetime(r['end_ts_utc'], utc=True)} | {r['joint_p_value']:.4g} | {r['amp_pct']:.4f} |\n"
            )


def make_one_graph(
    df: pd.DataFrame,
    corr_df: pd.DataFrame,
    diurnal_model: sm.regression.linear_model.RegressionResultsWrapper,
    prog_daily: pd.DataFrame,
    prog_detail: pd.DataFrame,
    wk: pd.DataFrame,
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=260, constrained_layout=True)

    # A) Pressure relation
    ax = axes[0, 0]
    ax.scatter(df["pressure_hPa"], df["rate_cpm"], s=7, alpha=0.15, color="#4c78a8")
    z = np.polyfit(df["pressure_hPa"], df["rate_cpm"], 1)
    xp = np.linspace(df["pressure_hPa"].min(), df["pressure_hPa"].max(), 300)
    ax.plot(xp, z[0] * xp + z[1], color="#e45756", linewidth=2.0)
    ax.set_title("A. Muon Rate vs Pressure")
    ax.set_xlabel("Pressure (hPa)")
    ax.set_ylabel("Rate (counts/min)")

    # B) Corrected diurnal fold
    ax = axes[0, 1]
    hourly = corr_df.groupby(corr_df.index.tz_convert(LOCAL_TZ).hour)["rate_atm_corr"].agg(["mean", "std", "count"]).reindex(np.arange(24))
    sem = hourly["std"] / np.sqrt(hourly["count"])
    xh = np.arange(24)
    ax.errorbar(xh, hourly["mean"], yerr=sem, fmt="o", color="#4c78a8", capsize=3, linewidth=1.2, label="Hourly mean ± SEM")
    a = float(diurnal_model.params["sin24"])
    b = float(diurnal_model.params["cos24"])
    hf = np.linspace(0, 24, 241)
    harm = np.exp(a * np.sin(OMEGA * hf) + b * np.cos(OMEGA * hf))
    harm = harm / harm.mean() * float(corr_df["rate_atm_corr"].mean())
    ax.plot(hf, harm, color="#e45756", linewidth=2.1, label="24h fit")
    ax.set_title("B. Corrected Diurnal Fold")
    ax.set_xlabel("Local hour")
    ax.set_ylabel("Corrected rate (counts/min)")
    ax.set_xticks(np.arange(0, 24, 2))
    ax.legend(fontsize=8)

    # C) Progression of p-value (smoothed daily trend + faint high-res)
    ax = axes[1, 0]
    ax.plot(
        prog_detail["elapsed_days"],
        prog_detail["joint_p_value"],
        color="#9ecae1",
        linewidth=1.0,
        alpha=0.55,
        label="High-res checkpoints",
    )
    ax.plot(
        prog_daily["elapsed_days"],
        prog_daily["joint_p_value"],
        color="#4c78a8",
        linewidth=2.2,
        label="Daily-collapsed trend",
    )
    best_so_far = np.minimum.accumulate(prog_detail["joint_p_value"].to_numpy())
    ax.plot(prog_detail["elapsed_days"], best_so_far, color="#2ca02c", linewidth=1.3, linestyle="--", label="Best-so-far p")

    ax.axhline(0.05, color="black", linestyle="--", linewidth=1.0)
    ax.set_yscale("log")
    ax.set_title("C. Diurnal Significance Progression")
    ax.set_xlabel("Elapsed days from start")
    ax.set_ylabel("Joint p-value (log)")

    first_detail = first_significant_row(prog_detail)
    if first_detail is not None:
        ax.scatter([first_detail["elapsed_days"]], [first_detail["joint_p_value"]], color="#e45756", s=55, zorder=5)
        ax.text(
            first_detail["elapsed_days"],
            first_detail["joint_p_value"] * 1.15,
            f"first <0.05\n{first_detail['elapsed_days']:.1f} d",
            fontsize=8,
        )
    ax.legend(fontsize=8)

    # D) Week checkpoints
    ax = axes[1, 1]
    xs = np.arange(len(wk))
    bars = ax.bar(xs, -np.log10(np.clip(wk["joint_p_value"], 1e-12, 1.0)), color="#72b7b2", alpha=0.9)
    ax.axhline(-np.log10(0.05), color="black", linestyle="--", linewidth=1.0)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"W{k}" for k in wk["target_days"] // 7])
    ax.set_title("D. Week Checkpoints (-log10 p)")
    ax.set_xlabel("Checkpoint")
    ax.set_ylabel("-log10(p)")
    for b, p, n in zip(bars, wk["joint_p_value"], wk["n_bins"]):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.03, f"p={p:.3g}\nn={int(n)}", ha="center", fontsize=8)

    fig.suptitle("Muon Analysis One-Graph Summary", fontsize=14)
    fig.savefig(FIG_DIR / "figure_summary_one_graph.png", bbox_inches="tight")


def main() -> None:
    FIG_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    df = load_data()
    atm = fit_atmospheric(df)
    di = fit_diurnal(df)
    corr = corrected_series(df, atm)

    prog_detail = cumulative_progression(df)
    prog_daily = collapse_progression_to_daily(prog_detail)

    prog_daily.to_csv(RESULTS_DIR / "diurnal_progression_all_data.csv", index=False)
    prog_detail.to_csv(RESULTS_DIR / "diurnal_progression_detailed.csv", index=False)

    wk = weekly_checkpoints(prog_daily, [7, 14, 21, 28])
    wk.to_csv(RESULTS_DIR / "diurnal_progression_checkpoints.csv", index=False)

    write_report(df, prog_detail, prog_daily, wk)
    make_one_graph(df, corr, di, prog_daily, prog_detail, wk)

    print(f"Saved: {RESULTS_DIR / 'diurnal_progression_all_data.csv'}")
    print(f"Saved: {RESULTS_DIR / 'diurnal_progression_detailed.csv'}")
    print(f"Saved: {RESULTS_DIR / 'diurnal_progression_checkpoints.csv'}")
    print(f"Saved: {RESULTS_DIR / 'diurnal_progression_report.md'}")
    print(f"Saved: {FIG_DIR / 'figure_summary_one_graph.png'}")


if __name__ == "__main__":
    main()
