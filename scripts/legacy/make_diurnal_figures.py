from __future__ import annotations

import argparse
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.signal import periodogram


LOCAL_TZ = ZoneInfo("America/New_York")
OMEGA = 2.0 * np.pi / 24.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate extended diurnal figure pack.")
    parser.add_argument("--data-file", default="clean_muon_dataset.csv", help="Path to clean_muon_dataset.csv")
    parser.add_argument("--out-dir", default="figures", help="Output directory for figures/tables")
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
    df["local_date"] = local.date
    df["sin24"] = np.sin(OMEGA * df["local_hour_float"])
    df["cos24"] = np.cos(OMEGA * df["local_hour_float"])
    return df


def session_label_map(df: pd.DataFrame) -> dict[int, str]:
    labels: dict[int, str] = {}
    for session in sorted(df["session"].unique()):
        sub = df[df["session"] == session]
        label = str(sub["run_label"].dropna().iloc[0]).strip() if "run_label" in sub.columns else ""
        labels[int(session)] = label if label else f"Session {int(session)}"
    return labels


def session_meta_table(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["session"]
    for col in ["run_number", "run_label", "run_date"]:
        if col in df.columns:
            cols.append(col)

    meta = df[cols].drop_duplicates(subset=["session"]).copy()
    if "run_number" in meta.columns:
        return meta.sort_values(["run_number", "session"])
    return meta.sort_values("session")


def select_sessions(df: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    available = sorted(df["session"].unique())
    if args.sessions is not None:
        keep = set(args.sessions)
        out = df[df["session"].isin(keep)].copy()
    else:
        # default to full dataset for this script
        out = df.copy()

    if out.empty:
        raise RuntimeError(f"No rows left after session filter. Available: {available}")
    return out


def fit_atmospheric_model(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    df["dP"] = df["pressure_hPa"] - float(df["pressure_hPa"].mean())
    df["dT"] = df["temp_C"] - float(df["temp_C"].mean())

    x = df[["dP", "dT"]].copy()
    if df["session"].nunique() > 1:
        dummies = pd.get_dummies(df["session"].astype(str), prefix="sess", drop_first=True, dtype=float)
        x = pd.concat([x, dummies], axis=1)

    x = sm.add_constant(x, has_constant="add").astype(float)
    model = sm.OLS(df["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    return model


def fit_diurnal_model(df: pd.DataFrame) -> sm.regression.linear_model.RegressionResultsWrapper:
    x = df[["dP", "dT", "sin24", "cos24"]].copy()
    if df["session"].nunique() > 1:
        dummies = pd.get_dummies(df["session"].astype(str), prefix="sess", drop_first=True, dtype=float)
        x = pd.concat([x, dummies], axis=1)

    x = sm.add_constant(x, has_constant="add").astype(float)
    model = sm.OLS(df["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    return model


def apply_atmospheric_correction(df: pd.DataFrame, model: sm.regression.linear_model.RegressionResultsWrapper) -> pd.DataFrame:
    out = df.copy()
    out["rate_atm_corr"] = out["rate_cpm"] * np.exp(-(model.params["dP"] * out["dP"] + model.params["dT"] * out["dT"]))
    out["raw_anom_pct"] = 100.0 * (out["rate_cpm"] / out["rate_cpm"].mean() - 1.0)
    out["corr_anom_pct"] = 100.0 * (out["rate_atm_corr"] / out["rate_atm_corr"].mean() - 1.0)
    return out


def ensure_plot_style() -> None:
    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except Exception:
        plt.style.use("ggplot")


def color_map_for_sessions(sessions: list[int]) -> dict[int, tuple[float, float, float, float]]:
    cmap = plt.get_cmap("tab10")
    return {s: cmap(i % 10) for i, s in enumerate(sorted(sessions))}


def plot_hourly_fold_by_session(
    df: pd.DataFrame,
    out_dir: Path,
    session_colors: dict[int, tuple],
    session_labels: dict[int, str],
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharex=True)

    for session in sorted(df["session"].unique()):
        sub = df[df["session"] == session]
        h_raw = sub.groupby("local_hour")["rate_cpm"].mean().reindex(np.arange(24))
        h_cor = sub.groupby("local_hour")["rate_atm_corr"].mean().reindex(np.arange(24))
        axes[0].plot(
            np.arange(24),
            h_raw.values,
            marker="o",
            linewidth=1.8,
            label=session_labels[int(session)],
            color=session_colors[session],
        )
        axes[1].plot(
            np.arange(24),
            h_cor.values,
            marker="o",
            linewidth=1.8,
            label=session_labels[int(session)],
            color=session_colors[session],
        )

    axes[0].set_title("Raw Rate Folded by Local Hour")
    axes[1].set_title("Atmosphere-corrected Rate Folded by Local Hour")
    axes[0].set_ylabel("Rate (counts/min)")
    for ax in axes:
        ax.set_xlabel("Local Hour")
        ax.set_xticks(np.arange(0, 24, 2))
        ax.legend(fontsize=9)

    fig.suptitle("Diurnal Fold by Session", fontsize=14)
    fig.tight_layout()
    fig.savefig(out_dir / "diurnal_full_01_fold_by_session.png", dpi=300)
    plt.close(fig)


def plot_overall_fold_with_sem(df: pd.DataFrame, diurnal_model: sm.regression.linear_model.RegressionResultsWrapper, out_dir: Path) -> None:
    hourly = (
        df.groupby("local_hour")["rate_atm_corr"]
        .agg(mean_rate="mean", std_rate="std", n="size")
        .reindex(np.arange(24))
    )
    sem = hourly["std_rate"] / np.sqrt(hourly["n"])

    a = float(diurnal_model.params["sin24"])
    b = float(diurnal_model.params["cos24"])
    h_fine = np.linspace(0.0, 24.0, 241)
    harmonic = np.exp(a * np.sin(OMEGA * h_fine) + b * np.cos(OMEGA * h_fine))
    harmonic = harmonic / harmonic.mean() * float(df["rate_atm_corr"].mean())

    plt.figure(figsize=(9, 5.5))
    plt.errorbar(np.arange(24), hourly["mean_rate"], yerr=sem, fmt="o", capsize=3, linewidth=1.3, label="Hourly mean +/- SEM")
    plt.plot(h_fine, harmonic, linewidth=2.2, label="24h harmonic fit")
    plt.xlabel("Local Hour")
    plt.ylabel("Corrected Rate (counts/min)")
    plt.title("Overall Corrected Diurnal Fold with Uncertainty")
    plt.xticks(np.arange(0, 24, 2))
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "diurnal_full_02_overall_fold_sem.png", dpi=300)
    plt.close()


def plot_hourly_boxplot(df: pd.DataFrame, out_dir: Path) -> None:
    data_by_hour = [df.loc[df["local_hour"] == h, "rate_atm_corr"].values for h in range(24)]
    plt.figure(figsize=(12, 5.5))
    bp = plt.boxplot(data_by_hour, positions=np.arange(24), widths=0.6, patch_artist=True, showfliers=False)
    for patch, h in zip(bp["boxes"], range(24)):
        patch.set_facecolor(plt.get_cmap("viridis")(h / 23 if h > 0 else 0.0))
        patch.set_alpha(0.65)
    means = [np.mean(x) if len(x) else np.nan for x in data_by_hour]
    plt.plot(np.arange(24), means, color="black", marker="o", linewidth=1.5, label="Hourly mean")
    plt.xlabel("Local Hour")
    plt.ylabel("Corrected Rate (counts/min)")
    plt.title("Distribution of Corrected Rate by Local Hour")
    plt.xticks(np.arange(0, 24, 2))
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_dir / "diurnal_full_03_hourly_boxplot.png", dpi=300)
    plt.close()


def plot_heatmaps(df: pd.DataFrame, out_dir: Path) -> None:
    raw_pivot = df.pivot_table(index="local_date", columns="local_hour", values="raw_anom_pct", aggfunc="mean")
    cor_pivot = df.pivot_table(index="local_date", columns="local_hour", values="corr_anom_pct", aggfunc="mean")

    v = float(np.nanpercentile(np.abs(np.concatenate([raw_pivot.values.flatten(), cor_pivot.values.flatten()])), 95))
    if not np.isfinite(v) or v <= 0:
        v = 3.0

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, constrained_layout=True)
    im1 = axes[0].imshow(raw_pivot.values, aspect="auto", cmap="RdBu_r", vmin=-v, vmax=v)
    axes[0].set_title("Raw Rate Anomaly Heatmap (Date x Local Hour)")
    axes[0].set_ylabel("Local Date")

    im2 = axes[1].imshow(cor_pivot.values, aspect="auto", cmap="RdBu_r", vmin=-v, vmax=v)
    axes[1].set_title("Corrected Rate Anomaly Heatmap (Date x Local Hour)")
    axes[1].set_ylabel("Local Date")
    axes[1].set_xlabel("Local Hour")

    hour_ticks = np.arange(0, 24, 2)
    axes[1].set_xticks(hour_ticks)
    axes[1].set_xticklabels(hour_ticks)

    date_labels = [str(d) for d in raw_pivot.index]
    if len(date_labels) <= 12:
        axes[0].set_yticks(np.arange(len(date_labels)))
        axes[0].set_yticklabels(date_labels)
        axes[1].set_yticks(np.arange(len(date_labels)))
        axes[1].set_yticklabels([str(d) for d in cor_pivot.index])

    cbar = fig.colorbar(im2, ax=axes, location="right", shrink=0.95, fraction=0.03, pad=0.02)
    cbar.set_label("Anomaly (%)")
    fig.savefig(out_dir / "diurnal_full_04_heatmaps_raw_vs_corrected.png", dpi=300)
    plt.close(fig)


def daily_harmonic_fit_table(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for (session, local_date), sub in df.groupby(["session", "local_date"]):
        if len(sub) < 72:
            continue
        x = sm.add_constant(
            pd.DataFrame(
                {
                    "sin24": np.sin(OMEGA * sub["local_hour_float"]),
                    "cos24": np.cos(OMEGA * sub["local_hour_float"]),
                },
                index=sub.index,
            ),
            has_constant="add",
        ).astype(float)
        y = sub["rate_atm_corr"].astype(float)
        m = sm.OLS(y, x).fit()

        a = float(m.params["sin24"])
        b = float(m.params["cos24"])
        amp_cpm = float(np.sqrt(a * a + b * b))
        amp_pct = 100.0 * amp_cpm / float(sub["rate_atm_corr"].mean())
        peak_hour = float((24.0 * np.arctan2(a, b) / (2.0 * np.pi)) % 24.0)
        p_joint = float(m.f_test("sin24=0, cos24=0").pvalue)

        rows.append(
            {
                "session": int(session),
                "local_date": str(local_date),
                "n_bins": int(len(sub)),
                "amp_cpm": amp_cpm,
                "amp_pct": amp_pct,
                "peak_hour_local": peak_hour,
                "p_value": p_joint,
                "r_squared": float(m.rsquared),
            }
        )

    columns = ["session", "local_date", "n_bins", "amp_cpm", "amp_pct", "peak_hour_local", "p_value", "r_squared"]
    return pd.DataFrame(rows, columns=columns)


def plot_daily_amp_outlier_flag(
    daily: pd.DataFrame,
    out_dir: Path,
    session_colors: dict[int, tuple],
    session_labels: dict[int, str],
) -> None:
    if daily.empty:
        return

    day = daily.copy()
    day["local_date"] = pd.to_datetime(day["local_date"], errors="coerce")
    day = day.dropna(subset=["local_date", "amp_pct", "n_bins", "session"]).copy()
    if day.empty:
        return

    q1 = float(day["amp_pct"].quantile(0.25))
    q3 = float(day["amp_pct"].quantile(0.75))
    iqr = q3 - q1
    outlier_threshold = q3 + 1.5 * iqr
    day["is_amp_outlier"] = day["amp_pct"] > outlier_threshold

    # Ensure at least one highlighted point if IQR threshold finds none.
    if not bool(day["is_amp_outlier"].any()):
        max_idx = day["amp_pct"].idxmax()
        day.loc[max_idx, "is_amp_outlier"] = True

    plt.figure(figsize=(12, 5.8))
    for session in sorted(day["session"].unique()):
        sub = day[day["session"] == session]
        sizes = np.clip((sub["n_bins"] / sub["n_bins"].max()) * 120.0, 35.0, 130.0)
        plt.scatter(
            sub["local_date"],
            sub["amp_pct"],
            s=sizes,
            alpha=0.75,
            color=session_colors[int(session)],
            label=session_labels[int(session)],
            edgecolors="none",
        )

    flagged = day[day["is_amp_outlier"]]
    plt.scatter(
        flagged["local_date"],
        flagged["amp_pct"],
        s=180,
        facecolors="none",
        edgecolors="black",
        linewidths=1.6,
        label="Amplitude outlier day",
    )

    for _, row in flagged.iterrows():
        plt.annotate(
            f"{row['local_date'].date()} ({int(row['n_bins'])} bins)",
            (row["local_date"], row["amp_pct"]),
            xytext=(8, 8),
            textcoords="offset points",
            fontsize=8,
        )

    plt.ylabel("Daily 24h Fit Amplitude (%)")
    plt.xlabel("Local Date")
    plt.title("Daily Diurnal Amplitude with Outlier Flag (marker size = bins/day)")
    plt.legend(ncol=3, fontsize=8)
    plt.tight_layout()
    plt.savefig(out_dir / "diurnal_full_08_daily_amp_outlier_flag.png", dpi=300)
    plt.close()


def fit_diurnal_metrics(df: pd.DataFrame) -> tuple[float, float]:
    if df.empty:
        return np.nan, np.nan

    x = df[["dP", "dT", "sin24", "cos24"]].copy()
    if df["session"].nunique() > 1:
        dummies = pd.get_dummies(df["session"].astype(str), prefix="sess", drop_first=True, dtype=float)
        x = pd.concat([x, dummies], axis=1)
    x = sm.add_constant(x, has_constant="add").astype(float)
    m = sm.OLS(df["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 6})

    p_joint = float(m.f_test("sin24=0, cos24=0").pvalue)
    amp_pct = float(np.sqrt(m.params["sin24"] ** 2 + m.params["cos24"] ** 2) * 100.0)
    return p_joint, amp_pct


def diurnal_sensitivity_table(df: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []

    p_base, amp_base = fit_diurnal_metrics(df)
    rows.append(
        {
            "scenario": "all_data",
            "n_bins": int(len(df)),
            "joint_p_value": p_base,
            "amp_pct": amp_base,
            "note": "",
        }
    )

    # Sensitivity to the strongest daily-amplitude outlier.
    if not daily.empty:
        outlier_day = daily.sort_values("amp_pct", ascending=False).iloc[0]
        day_str = str(outlier_day["local_date"])
        n_day = int(outlier_day["n_bins"])
        cut = df[df["local_date"].astype(str) != day_str].copy()
        if len(cut) >= 200:
            p_cut, amp_cut = fit_diurnal_metrics(cut)
            rows.append(
                {
                    "scenario": "exclude_max_amp_day",
                    "n_bins": int(len(cut)),
                    "joint_p_value": p_cut,
                    "amp_pct": amp_cut,
                    "note": f"removed {day_str} ({n_day} bins)",
                }
            )

    # Exclude partial days to test impact of short-coverage days.
    day_counts = df.groupby("local_date").size()
    keep_days = day_counts[day_counts >= 120].index
    cut_partial = df[df["local_date"].isin(keep_days)].copy()
    if len(cut_partial) >= 200:
        p_cut, amp_cut = fit_diurnal_metrics(cut_partial)
        rows.append(
            {
                "scenario": "exclude_partial_days_lt120bins",
                "n_bins": int(len(cut_partial)),
                "joint_p_value": p_cut,
                "amp_pct": amp_cut,
                "note": "kept days with >=120 bins",
            }
        )

    # Remove extreme tails of raw rate distribution (robustness check).
    q_lo = float(df["rate_cpm"].quantile(0.005))
    q_hi = float(df["rate_cpm"].quantile(0.995))
    cut_rate = df[(df["rate_cpm"] >= q_lo) & (df["rate_cpm"] <= q_hi)].copy()
    if len(cut_rate) >= 200:
        p_cut, amp_cut = fit_diurnal_metrics(cut_rate)
        rows.append(
            {
                "scenario": "trim_rate_0p5pct_tails",
                "n_bins": int(len(cut_rate)),
                "joint_p_value": p_cut,
                "amp_pct": amp_cut,
                "note": f"rate_cpm in [{q_lo:.2f}, {q_hi:.2f}]",
            }
        )

    return pd.DataFrame(rows)


def plot_diurnal_sensitivity(sens: pd.DataFrame, out_dir: Path) -> None:
    if sens.empty:
        return

    s = sens.copy()
    s["label"] = s["scenario"].str.replace("_", " ", regex=False)
    x = np.arange(len(s))

    fig, ax1 = plt.subplots(figsize=(11.5, 5.8))
    bars = ax1.bar(x, s["joint_p_value"], color="#4c78a8", alpha=0.75, label="Joint p-value")
    ax1.axhline(0.05, color="black", linestyle="--", linewidth=1.0, label="p = 0.05")
    ax1.set_yscale("log")
    ax1.set_ylabel("Joint p-value (log scale)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(s["label"], rotation=20, ha="right")
    ax1.set_title("Diurnal Significance Sensitivity to Outliers and Filtering")

    ax2 = ax1.twinx()
    ax2.plot(x, s["amp_pct"], color="#f58518", marker="o", linewidth=2.0, label="Amplitude (%)")
    ax2.set_ylabel("24h Harmonic Amplitude (%)")

    for i, row in s.iterrows():
        ax1.text(
            i,
            max(row["joint_p_value"] * 1.15, 0.0006),
            f"n={int(row['n_bins'])}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2, loc="upper right", fontsize=8)

    fig.tight_layout()
    fig.savefig(out_dir / "diurnal_sensitivity_outlier_check.png", dpi=300)
    plt.close(fig)


def plot_daily_amp_phase(
    daily: pd.DataFrame,
    out_dir: Path,
    session_colors: dict[int, tuple],
    session_labels: dict[int, str],
) -> None:
    if daily.empty:
        return

    daily = daily.copy()
    daily["local_date"] = pd.to_datetime(daily["local_date"]).dt.date

    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)

    for session in sorted(daily["session"].unique()):
        sub = daily[daily["session"] == session]
        label = session_labels[int(session)]
        axes[0].plot(sub["local_date"], sub["amp_pct"], marker="o", linewidth=1.8, color=session_colors[session], label=label)
        axes[1].plot(
            sub["local_date"],
            sub["peak_hour_local"],
            marker="o",
            linewidth=1.8,
            color=session_colors[session],
            label=label,
        )
        axes[2].plot(
            sub["local_date"],
            -np.log10(np.clip(sub["p_value"], 1e-12, 1.0)),
            marker="o",
            linewidth=1.8,
            color=session_colors[session],
            label=label,
        )

    axes[0].set_ylabel("Daily Amp (%)")
    axes[1].set_ylabel("Peak Hour")
    axes[1].set_ylim(0, 24)
    axes[2].set_ylabel("-log10(p)")
    axes[2].set_xlabel("Local Date")
    axes[2].axhline(-np.log10(0.05), color="black", linestyle="--", linewidth=1.0, label="p=0.05")

    axes[0].set_title("Day-by-day Diurnal Fit Diagnostics")
    axes[0].legend(ncol=3, fontsize=8)
    axes[1].legend(ncol=3, fontsize=8)
    axes[2].legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "diurnal_full_05_daily_amp_phase.png", dpi=300)
    plt.close(fig)


def plot_periodogram_by_session(
    df: pd.DataFrame,
    out_dir: Path,
    session_colors: dict[int, tuple],
    session_labels: dict[int, str],
) -> pd.DataFrame:
    rows: list[dict] = []
    plt.figure(figsize=(10.5, 5.5))

    for session in sorted(df["session"].unique()):
        sub = df[df["session"] == session].copy().sort_index()

        full_idx = pd.date_range(sub.index.min(), sub.index.max(), freq="10min", tz="UTC")
        y = sub["corr_anom_pct"].reindex(full_idx).interpolate(limit=3).dropna()
        if len(y) < 200:
            continue

        f, p = periodogram(y.values, fs=6.0, window="hann", scaling="density")
        mask = f > 0
        f = f[mask]
        p = p[mask]
        period_h = 1.0 / f
        sel = (period_h >= 6) & (period_h <= 72)
        period_h = period_h[sel]
        p = p[sel]
        if len(period_h) == 0:
            continue
        order = np.argsort(period_h)
        period_h = period_h[order]
        p = p[order]

        plt.plot(
            period_h,
            p,
            marker="o",
            markersize=3.5,
            linewidth=1.2,
            color=session_colors[session],
            label=session_labels[int(session)],
        )

        top_idx = int(np.argmax(p))
        rows.append(
            {
                "session": int(session),
                "top_period_h": float(period_h[top_idx]),
                "top_power": float(p[top_idx]),
                "power_near_24h": float(p[int(np.argmin(np.abs(period_h - 24.0)))]),
                "power_near_12h": float(p[int(np.argmin(np.abs(period_h - 12.0)))]),
            }
        )

    plt.axvline(24.0, color="black", linestyle="--", linewidth=1.0, label="24 h")
    plt.axvline(12.0, color="gray", linestyle=":", linewidth=1.0, label="12 h")
    plt.xlabel("Period (hours)")
    plt.ylabel("Power Spectral Density")
    plt.title("Periodogram of Corrected Rate Anomaly by Session")
    plt.legend(ncol=2, fontsize=9)
    plt.tight_layout()
    plt.savefig(out_dir / "diurnal_full_06_periodogram_by_session.png", dpi=300)
    plt.close()

    columns = ["session", "top_period_h", "top_power", "power_near_24h", "power_near_12h"]
    return pd.DataFrame(rows, columns=columns)


def cumulative_diurnal_table(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []

    for session in sorted(df["session"].unique()):
        sub = df[df["session"] == session].copy().sort_index()
        if len(sub) < 200:
            continue

        for n in range(200, len(sub) + 1, 24):
            chunk = sub.iloc[:n]
            x = sm.add_constant(chunk[["dP", "dT", "sin24", "cos24"]], has_constant="add").astype(float)
            m = sm.OLS(chunk["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
            p_joint = float(m.f_test("sin24=0, cos24=0").pvalue)
            amp = float(np.sqrt(m.params["sin24"] ** 2 + m.params["cos24"] ** 2) * 100.0)
            rows.append(
                {
                    "session": int(session),
                    "n_bins": int(n),
                    "end_ts_utc": chunk.index[-1],
                    "diurnal_p_value": p_joint,
                    "diurnal_amp_pct": amp,
                }
            )

    columns = ["session", "n_bins", "end_ts_utc", "diurnal_p_value", "diurnal_amp_pct"]
    return pd.DataFrame(rows, columns=columns)


def plot_cumulative(
    diag: pd.DataFrame,
    out_dir: Path,
    session_colors: dict[int, tuple],
    session_labels: dict[int, str],
) -> None:
    if diag.empty:
        return

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)

    for session in sorted(diag["session"].unique()):
        sub = diag[diag["session"] == session]
        label = session_labels[int(session)]
        axes[0].plot(sub["end_ts_utc"], sub["diurnal_p_value"], linewidth=1.8, color=session_colors[session], label=label)
        axes[1].plot(sub["end_ts_utc"], sub["diurnal_amp_pct"], linewidth=1.8, color=session_colors[session], label=label)

    axes[0].axhline(0.05, color="black", linestyle="--", linewidth=1.0)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Diurnal p-value (log scale)")
    axes[0].set_title("Cumulative 24h Harmonic Test by Session")
    axes[0].legend(ncol=3, fontsize=8)

    axes[1].set_ylabel("Estimated 24h Amp (%)")
    axes[1].set_xlabel("UTC Time")
    axes[1].legend(ncol=3, fontsize=8)

    fig.tight_layout()
    fig.savefig(out_dir / "diurnal_full_07_cumulative_pvalue_amp.png", dpi=300)
    plt.close(fig)


def write_summary(
    df: pd.DataFrame,
    atm_model: sm.regression.linear_model.RegressionResultsWrapper,
    diurnal_model: sm.regression.linear_model.RegressionResultsWrapper,
    daily: pd.DataFrame,
    period: pd.DataFrame,
    cumulative: pd.DataFrame,
    sensitivity: pd.DataFrame,
    out_dir: Path,
) -> None:
    amp = float(np.sqrt(diurnal_model.params["sin24"] ** 2 + diurnal_model.params["cos24"] ** 2) * 100.0)
    p_joint = float(diurnal_model.f_test("sin24=0, cos24=0").pvalue)
    labels = session_label_map(df)

    with open(out_dir / "diurnal_full_summary.txt", "w", encoding="utf-8") as f:
        f.write("Extended Diurnal Figure Pack Summary\n")
        f.write("====================================\n")
        f.write(f"N bins: {len(df)}\n")
        f.write(f"Runs: {', '.join(labels[int(s)] for s in sorted(df['session'].unique()))}\n")
        f.write(f"Session IDs: {', '.join(str(s) for s in sorted(df['session'].unique()))}\n")
        f.write(f"UTC span: {df.index.min()} to {df.index.max()}\n\n")

        f.write("Atmospheric model:\n")
        f.write(f"  beta = {-100.0 * atm_model.params['dP']:.4f} %/hPa\n")
        f.write(f"  p(beta) = {atm_model.pvalues['dP']:.3g}\n")
        f.write(f"  p(temp) = {atm_model.pvalues['dT']:.3g}\n\n")

        f.write("Diurnal model:\n")
        f.write(f"  24h harmonic amplitude = {amp:.4f} %\n")
        f.write(f"  joint p(sin24, cos24) = {p_joint:.3g}\n")
        f.write(f"  R^2 = {diurnal_model.rsquared:.5f}\n\n")

        if not daily.empty:
            f.write("Daily fits:\n")
            f.write(f"  days fitted = {len(daily)}\n")
            f.write(f"  median daily amp = {daily['amp_pct'].median():.4f} %\n")
            f.write(f"  min p-value across days = {daily['p_value'].min():.3g}\n\n")

        if not period.empty:
            f.write("Periodogram peaks by session:\n")
            for _, row in period.sort_values("session").iterrows():
                label = str(row["run_label"]).strip() if "run_label" in period.columns else ""
                if not label:
                    label = f"session {int(row['session'])}"
                f.write(
                    f"  {label}: top period {row['top_period_h']:.2f} h, "
                    f"power24={row['power_near_24h']:.6g}, power12={row['power_near_12h']:.6g}\n"
                )
            f.write("\n")

        if not cumulative.empty:
            f.write("Cumulative test:\n")
            f.write(f"  min cumulative p-value = {cumulative['diurnal_p_value'].min():.3g}\n")

        if not sensitivity.empty:
            f.write("\nOutlier/robustness sensitivity:\n")
            for _, row in sensitivity.iterrows():
                f.write(
                    f"  {row['scenario']}: p={row['joint_p_value']:.4g}, "
                    f"amp={row['amp_pct']:.4f} %, n={int(row['n_bins'])}"
                )
                note = str(row.get("note", "")).strip()
                if note:
                    f.write(f", {note}")
                f.write("\n")


def main() -> None:
    args = parse_args()
    data_file = Path(args.data_file)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)

    ensure_plot_style()

    df = load_data(data_file)
    df = select_sessions(df, args)
    session_labels = session_label_map(df)
    session_meta = session_meta_table(df)

    session_colors = color_map_for_sessions(sorted(df["session"].unique()))

    atm_model = fit_atmospheric_model(df)
    diurnal_model = fit_diurnal_model(df)
    corr_df = apply_atmospheric_correction(df, atm_model)

    plot_hourly_fold_by_session(corr_df, out_dir, session_colors, session_labels)
    plot_overall_fold_with_sem(corr_df, diurnal_model, out_dir)
    plot_hourly_boxplot(corr_df, out_dir)
    plot_heatmaps(corr_df, out_dir)

    daily = daily_harmonic_fit_table(corr_df)
    daily = daily.merge(session_meta, on="session", how="left")
    daily.to_csv(out_dir / "diurnal_full_daily_fits.csv", index=False)
    plot_daily_amp_phase(daily, out_dir, session_colors, session_labels)
    plot_daily_amp_outlier_flag(daily, out_dir, session_colors, session_labels)

    period = plot_periodogram_by_session(corr_df, out_dir, session_colors, session_labels)
    period = period.merge(session_meta, on="session", how="left")
    period.to_csv(out_dir / "diurnal_full_periodogram_peaks.csv", index=False)

    cumulative = cumulative_diurnal_table(corr_df)
    cumulative = cumulative.merge(session_meta, on="session", how="left")
    cumulative.to_csv(out_dir / "diurnal_full_cumulative_table.csv", index=False)
    plot_cumulative(cumulative, out_dir, session_colors, session_labels)

    sensitivity = diurnal_sensitivity_table(corr_df, daily)
    sensitivity.to_csv(out_dir / "diurnal_outlier_sensitivity.csv", index=False)
    plot_diurnal_sensitivity(sensitivity, out_dir)

    group_cols = ["session"]
    for col in ["run_number", "run_label", "run_date"]:
        if col in corr_df.columns:
            group_cols.append(col)
    group_cols.append("local_hour")

    hourly = (
        corr_df.groupby(group_cols)
        .agg(
            raw_mean=("rate_cpm", "mean"),
            corr_mean=("rate_atm_corr", "mean"),
            corr_std=("rate_atm_corr", "std"),
            n=("rate_atm_corr", "size"),
        )
        .reset_index()
    )
    hourly.to_csv(out_dir / "diurnal_full_hourly_stats.csv", index=False)

    write_summary(corr_df, atm_model, diurnal_model, daily, period, cumulative, sensitivity, out_dir)

    print("Done.")
    print(f"Runs used: {', '.join(session_labels[int(s)] for s in sorted(corr_df['session'].unique()))}")
    print(f"Saved extended diurnal figure pack to: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
