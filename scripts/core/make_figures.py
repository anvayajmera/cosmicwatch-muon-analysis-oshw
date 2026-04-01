from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from scipy.stats import poisson
from statsmodels.stats.diagnostic import acorr_ljungbox

<<<<<<<< HEAD:scripts/analysis/make_figures.py
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT_DIR / "clean_muon_dataset.csv"
OUT_DIR = ROOT_DIR / "figures"
========

# ---------------------------
# CONFIG
# ---------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = PROJECT_ROOT / "results" / "clean_muon_dataset.csv"
FIG_DIR = PROJECT_ROOT / "figures"
RESULTS_DIR = PROJECT_ROOT / "results"
>>>>>>>> 509b85d (Reorganize analysis pipeline, regenerate outputs, and clean repo structure):scripts/core/make_figures.py
LOCAL_TZ = ZoneInfo("America/New_York")
HAC_MAXLAGS = 6
BIN_MINUTES = 10.0
ROLLING_BINS = 18


def reset_output_dir(out_dir: Path, keep_names: set[str] | None = None) -> None:
    keep = keep_names or set()
    out_dir.mkdir(exist_ok=True)
    for item in out_dir.iterdir():
        if item.is_file() and item.name not in keep:
            item.unlink()


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required dataset: {path}")

    raw = pd.read_csv(path)
    if "ts_utc" in raw.columns:
        ts_col = "ts_utc"
    else:
        ts_col = raw.columns[0]

    raw[ts_col] = pd.to_datetime(raw[ts_col], utc=True, errors="coerce", format="mixed")
    df = raw.dropna(subset=[ts_col]).set_index(ts_col).sort_index()

    required = ["muon_counts", "rate_cpm", "bmp_pressurePa_mean", "bmp_tempC_mean", "session"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Dataset missing required columns: {missing}")

    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
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

    p0 = float(df["pressure_hPa"].mean())
    t0 = float(df["temp_C"].mean())
    df["dP"] = df["pressure_hPa"] - p0
    df["dT"] = df["temp_C"] - t0

    local_ts = df.index.tz_convert(LOCAL_TZ)
    local_hour_float = local_ts.hour + local_ts.minute / 60.0 + local_ts.second / 3600.0
    omega = 2.0 * np.pi / 24.0
    df["local_hour_float"] = local_hour_float
    df["local_hour"] = local_ts.hour
    df["sin24"] = np.sin(omega * local_hour_float)
    df["cos24"] = np.cos(omega * local_hour_float)

<<<<<<<< HEAD:scripts/analysis/make_figures.py
    if {"euler_roll_deg_mean", "euler_pitch_deg_mean"}.issubset(df.columns):
        df["tilt_deg"] = np.sqrt(df["euler_roll_deg_mean"] ** 2 + df["euler_pitch_deg_mean"] ** 2)
    if {"linacc_x_mps2_mean", "linacc_y_mps2_mean", "linacc_z_mps2_mean"}.issubset(df.columns):
        df["linacc_mag"] = np.sqrt(
            df["linacc_x_mps2_mean"] ** 2 + df["linacc_y_mps2_mean"] ** 2 + df["linacc_z_mps2_mean"] ** 2
        )
    if {"gyro_x_rads_mean", "gyro_y_rads_mean", "gyro_z_rads_mean"}.issubset(df.columns):
        df["gyro_mag"] = np.sqrt(df["gyro_x_rads_mean"] ** 2 + df["gyro_y_rads_mean"] ** 2 + df["gyro_z_rads_mean"] ** 2)
    if {"mag_x_uT_mean", "mag_y_uT_mean", "mag_z_uT_mean"}.issubset(df.columns):
        df["mag_mag"] = np.sqrt(df["mag_x_uT_mean"] ** 2 + df["mag_y_uT_mean"] ** 2 + df["mag_z_uT_mean"] ** 2)
    if "cpu_tempC" in df.columns:
        df["cpu_temp_c"] = pd.to_numeric(df["cpu_tempC"], errors="coerce")

========
>>>>>>>> 509b85d (Reorganize analysis pipeline, regenerate outputs, and clean repo structure):scripts/core/make_figures.py
    return df


def session_label_map(df: pd.DataFrame) -> dict[int, str]:
    labels: dict[int, str] = {}
    for session in sorted(df["session"].unique()):
        sub = df[df["session"] == session]
        if "run_label" in sub.columns and not sub["run_label"].dropna().empty:
            label = str(sub["run_label"].dropna().iloc[0]).strip()
            labels[int(session)] = label if label else f"Session {int(session)}"
        else:
            labels[int(session)] = f"Session {int(session)}"
    return labels


def build_design(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    session_dummies = pd.get_dummies(df["session"].astype(int).astype(str), prefix="sess", drop_first=True, dtype=float)
    x = pd.concat([df[columns], session_dummies], axis=1)
    x = sm.add_constant(x, has_constant="add")
    return x.astype(float)


def fit_models(df: pd.DataFrame) -> dict[str, sm.regression.linear_model.RegressionResultsWrapper]:
    models: dict[str, sm.regression.linear_model.RegressionResultsWrapper] = {}

    x_pressure = build_design(df, ["dP"])
    x_atm = build_design(df, ["dP", "dT"])
    x_diurnal = build_design(df, ["dP", "dT", "sin24", "cos24"])

    models["pressure_only"] = sm.OLS(df["log_rate"], x_pressure).fit(
        cov_type="HAC", cov_kwds={"maxlags": HAC_MAXLAGS}
    )
    models["atmospheric"] = sm.OLS(df["log_rate"], x_atm).fit(
        cov_type="HAC", cov_kwds={"maxlags": HAC_MAXLAGS}
    )
    models["diurnal"] = sm.OLS(df["log_rate"], x_diurnal).fit(
        cov_type="HAC", cov_kwds={"maxlags": HAC_MAXLAGS}
    )

    models["poisson_diurnal"] = sm.GLM(
        df["muon_counts"],
        x_diurnal,
        family=sm.families.Poisson(),
        offset=np.log(np.full(len(df), BIN_MINUTES)),
    ).fit(cov_type="HC3")

    return models


def session_barometric_table(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for session, sub in df.groupby("session"):
        sub = sub.copy()
        if len(sub) < 50:
            continue

        run_number = None
        if "run_number" in sub.columns and sub["run_number"].notna().any():
            run_number = int(sub["run_number"].dropna().iloc[0])

        run_label = str(sub["run_label"].dropna().iloc[0]) if "run_label" in sub.columns else f"Session {int(session)}"
        run_date = str(sub["run_date"].dropna().iloc[0]) if "run_date" in sub.columns else ""

        sub["dP_s"] = sub["pressure_hPa"] - float(sub["pressure_hPa"].mean())
        sub["dT_s"] = sub["temp_C"] - float(sub["temp_C"].mean())
        x = sm.add_constant(sub[["dP_s", "dT_s"]], has_constant="add").astype(float)
        model = sm.OLS(sub["log_rate"], x).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_MAXLAGS})

        ci = model.conf_int().loc["dP_s"]
        rows.append(
            {
                "session": int(session),
                "run_number": run_number,
                "run_label": run_label,
                "run_date": run_date,
                "n_bins": int(len(sub)),
                "start_utc": sub.index.min(),
                "end_utc": sub.index.max(),
                "mean_rate_cpm": float(sub["rate_cpm"].mean()),
                "pressure_min_hPa": float(sub["pressure_hPa"].min()),
                "pressure_max_hPa": float(sub["pressure_hPa"].max()),
                "temp_min_C": float(sub["temp_C"].min()),
                "temp_max_C": float(sub["temp_C"].max()),
                "beta_pct_per_hPa": float(-100.0 * model.params["dP_s"]),
                "beta_ci95_low_pct_per_hPa": float(-100.0 * ci[1]),
                "beta_ci95_high_pct_per_hPa": float(-100.0 * ci[0]),
                "beta_pvalue": float(model.pvalues["dP_s"]),
                "temp_pvalue": float(model.pvalues["dT_s"]),
                "r_squared": float(model.rsquared),
            }
        )

    table = pd.DataFrame(rows)
    if table.empty:
        return table

    if "run_number" in table.columns and table["run_number"].notna().any():
        return table.sort_values(["run_number", "session"])
    return table.sort_values("session")


def correlation_table(df: pd.DataFrame) -> pd.DataFrame:
    # Keep correlation output tightly scoped to paper-relevant atmospheric predictors.
    candidates = ["pressure_hPa", "temp_C"]

    rows: list[dict] = []
    for col in candidates:
        if col not in df.columns:
            continue
        sub = df[["rate_cpm", col]].dropna()
        if len(sub) < 30:
            continue
        r, p = stats.pearsonr(sub["rate_cpm"], sub[col])
        rows.append(
            {
                "predictor": col,
                "n": int(len(sub)),
                "pearson_r": float(r),
                "r_squared": float(r**2),
                "p_value": float(p),
            }
        )

    if not rows:
        return pd.DataFrame(columns=["predictor", "n", "pearson_r", "r_squared", "p_value"])

    return pd.DataFrame(rows).sort_values("r_squared", ascending=False)


def model_coefficients_table(models: dict[str, object]) -> pd.DataFrame:
    rows: list[dict] = []
    for model_name, model in models.items():
        for term in model.params.index:
            ci = model.conf_int().loc[term]
            rows.append(
                {
                    "model": model_name,
                    "term": term,
                    "coef": float(model.params[term]),
                    "std_err": float(model.bse[term]),
                    "p_value": float(model.pvalues[term]),
                    "ci95_low": float(ci[0]),
                    "ci95_high": float(ci[1]),
                }
            )
    return pd.DataFrame(rows)


def make_figures(df: pd.DataFrame, models: dict[str, object]) -> dict[str, float]:
    m_pressure = models["pressure_only"]
    m_atm = models["atmospheric"]
    m_diurnal = models["diurnal"]
    labels = session_label_map(df)

    beta = -float(m_atm.params["dP"])
    beta_pct = 100.0 * beta

    df["rate_pressure_corr"] = df["rate_cpm"] * np.exp(beta * df["dP"])
    df["rate_atm_corr"] = df["rate_cpm"] * np.exp(
        -(float(m_atm.params["dP"]) * df["dP"] + float(m_atm.params["dT"]) * df["dT"])
    )

    a_sin = float(m_diurnal.params["sin24"])
    b_cos = float(m_diurnal.params["cos24"])
    amp_frac = float(np.sqrt(a_sin**2 + b_cos**2))
    amp_pct = 100.0 * amp_frac
    amp_cpm = float(df["rate_atm_corr"].mean() * amp_frac)
    joint_p = float(m_diurnal.f_test("sin24 = 0, cos24 = 0").pvalue)

    peak_hour = float((24.0 * np.arctan2(a_sin, b_cos) / (2.0 * np.pi)) % 24.0)
    mean_counts = float(df["muon_counts"].mean())
    poisson_floor_pct = float(100.0 / np.sqrt(mean_counts))
    amp_vs_floor = float(amp_pct / poisson_floor_pct)

    plt.figure(figsize=(8, 5))
    for session in sorted(df["session"].unique()):
        sub = df[df["session"] == session]
        plt.scatter(sub["pressure_hPa"], sub["rate_cpm"], alpha=0.45, s=12, label=labels[int(session)])

    x = np.linspace(df["pressure_hPa"].min(), df["pressure_hPa"].max(), 300)
    p0 = float(df["pressure_hPa"].mean())
    y = np.exp(float(m_pressure.params["const"]) + float(m_pressure.params["dP"]) * (x - p0))
    plt.plot(x, y, color="black", linewidth=2.0, label="Log-linear atmospheric fit")
    plt.xlabel("Atmospheric Pressure (hPa)")
    plt.ylabel("Muon Count Rate (counts/min)")
    plt.title("Muon Count Rate vs Atmospheric Pressure")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "figure1_rate_vs_pressure.png", dpi=300)
    plt.close()

    plt.figure(figsize=(11, 5))
    for session in sorted(df["session"].unique()):
        sub = df[df["session"] == session]
        smooth = sub["rate_cpm"].rolling(ROLLING_BINS, center=True, min_periods=max(3, ROLLING_BINS // 3)).mean()
        plt.scatter(sub.index, sub["rate_cpm"], s=8, alpha=0.18, label=f"{labels[int(session)]} raw")
        plt.plot(sub.index, smooth, linewidth=2.0, label=f"{labels[int(session)]} 3h mean")
    plt.xlabel("Time (UTC)")
    plt.ylabel("Muon Count Rate (counts/min)")
    plt.title("Muon Count Rate vs Time (10-min bins with 3h trend)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "figure2_rate_vs_time.png", dpi=300)
    plt.close()

    plt.figure(figsize=(11, 5))
    for session in sorted(df["session"].unique()):
        sub = df[df["session"] == session]
        raw_anom = 100.0 * (sub["rate_cpm"] / sub["rate_cpm"].mean() - 1.0)
        corr_anom = 100.0 * (sub["rate_atm_corr"] / sub["rate_atm_corr"].mean() - 1.0)
        raw_smooth = raw_anom.rolling(ROLLING_BINS, center=True, min_periods=max(3, ROLLING_BINS // 3)).mean()
        corr_smooth = corr_anom.rolling(ROLLING_BINS, center=True, min_periods=max(3, ROLLING_BINS // 3)).mean()
        plt.plot(
            sub.index,
            raw_smooth,
            linewidth=1.8,
            alpha=0.65,
            linestyle="--",
            label=f"{labels[int(session)]} raw anomaly",
        )
        plt.plot(sub.index, corr_smooth, linewidth=2.0, label=f"{labels[int(session)]} corrected anomaly")
    plt.xlabel("Time (UTC)")
    plt.ylabel("Rate Anomaly (%)")
    plt.title("Raw vs Atmosphere-corrected Muon Rate Anomaly (3h trend)")
    plt.axhline(0.0, color="black", linewidth=0.8, alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "figure3_corrected_rate_vs_time.png", dpi=300)
    plt.close()

    counts = df["muon_counts"].round().astype(int).values
    lam = counts.mean()
    xk = np.arange(counts.min(), counts.max() + 1)

    plt.figure(figsize=(8, 5))
    plt.hist(
        counts,
        bins=np.arange(counts.min(), counts.max() + 2) - 0.5,
        density=True,
        alpha=0.75,
        label="Observed",
    )
    plt.plot(xk, poisson.pmf(xk, lam), marker="o", linewidth=1.5, label=f"Poisson (lambda={lam:.2f})")
    plt.xlabel("Muon Counts per 10-minute Window")
    plt.ylabel("Probability Density")
    plt.title("Observed Count Distribution vs Poisson Model")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "figure4_poisson_histogram.png", dpi=300)
    plt.close()

    hourly = (
        df.groupby("local_hour")["rate_atm_corr"]
        .agg(mean_rate="mean", std_rate="std", n="size")
        .reindex(np.arange(24))
    )
    sem = hourly["std_rate"] / np.sqrt(hourly["n"])
    hourly_sem_pct = 100.0 * sem / hourly["mean_rate"]
    median_hourly_sem_pct = float(hourly_sem_pct.dropna().median())
    max_hourly_sem_pct = float(hourly_sem_pct.dropna().max())

    h_fine = np.linspace(0.0, 24.0, 241)
    omega = 2.0 * np.pi / 24.0
    harmonic = np.exp(a_sin * np.sin(omega * h_fine) + b_cos * np.cos(omega * h_fine))
    harmonic = harmonic / harmonic.mean() * float(df["rate_atm_corr"].mean())

    plt.figure(figsize=(8.5, 5))
    plt.errorbar(
        hourly.index,
        hourly["mean_rate"],
        yerr=sem,
        fmt="o",
        capsize=3,
        label="Hourly mean +/- SEM",
    )
    plt.plot(h_fine, harmonic, linewidth=2.0, label="Fitted 24-hour harmonic")
    plt.xlabel("Local Hour of Day")
    plt.ylabel("Atmosphere-corrected Rate (counts/min)")
    plt.title("Diurnal Fold After Atmospheric Correction")
    plt.xticks(np.arange(0, 24, 2))
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG_DIR / "figure5_diurnal_folded.png", dpi=300)
    plt.close()

<<<<<<<< HEAD:scripts/analysis/make_figures.py
    if "tilt_deg" in df.columns and df["tilt_deg"].notna().sum() > 30:
        sub = df[["tilt_deg"]].dropna()
        plt.figure(figsize=(11, 4.5))
        plt.plot(sub.index, sub["tilt_deg"])
        plt.xlabel("Time (UTC)")
        plt.ylabel("Tilt Angle (deg)")
        plt.title("Detector Tilt Angle vs Time")
        plt.tight_layout()
        plt.savefig(OUT_DIR / "appendix_tilt_vs_time.png", dpi=300)
        plt.close()

        plt.figure(figsize=(7, 5))
        plt.scatter(df["tilt_deg"], df["rate_cpm"], alpha=0.5)
        plt.xlabel("Tilt Angle (deg)")
        plt.ylabel("Muon Count Rate (counts/min)")
        plt.title("Muon Count Rate vs Tilt Angle")
        plt.tight_layout()
        plt.savefig(OUT_DIR / "appendix_rate_vs_tilt.png", dpi=300)
        plt.close()

    if "linacc_mag" in df.columns and df["linacc_mag"].notna().sum() > 30:
        sub = df[["linacc_mag"]].dropna()
        plt.figure(figsize=(11, 4.5))
        plt.plot(sub.index, sub["linacc_mag"])
        plt.xlabel("Time (UTC)")
        plt.ylabel("Linear Acceleration Magnitude (m/s^2)")
        plt.title("Linear Acceleration Magnitude vs Time")
        plt.tight_layout()
        plt.savefig(OUT_DIR / "appendix_linacc_vs_time.png", dpi=300)
        plt.close()

    if "mag_mag" in df.columns and df["mag_mag"].notna().sum() > 30:
        sub = df[["mag_mag"]].dropna()
        plt.figure(figsize=(11, 4.5))
        plt.plot(sub.index, sub["mag_mag"])
        plt.xlabel("Time (UTC)")
        plt.ylabel("Magnetic Field Magnitude (uT)")
        plt.title("Magnetic Field Magnitude vs Time")
        plt.tight_layout()
        plt.savefig(OUT_DIR / "appendix_mag_vs_time.png", dpi=300)
        plt.close()

========
>>>>>>>> 509b85d (Reorganize analysis pipeline, regenerate outputs, and clean repo structure):scripts/core/make_figures.py
    return {
        "beta_pct_per_hPa": beta_pct,
        "diurnal_joint_p": joint_p,
        "diurnal_amp_pct": amp_pct,
        "diurnal_amp_cpm": amp_cpm,
        "diurnal_peak_local_hour": peak_hour,
        "poisson_floor_pct_10min": poisson_floor_pct,
        "amp_vs_poisson_floor": amp_vs_floor,
        "median_hourly_sem_pct": median_hourly_sem_pct,
        "max_hourly_sem_pct": max_hourly_sem_pct,
    }


def main() -> None:
    keep_files = {
<<<<<<<< HEAD:scripts/analysis/make_figures.py
        "session_ingest_report.csv",
        "supplement_diurnal_by_run.png",
        "supplement_diurnal_hourly_stats.csv",
        "supplement_diurnal_summary.txt",
    }
    reset_output_dir(OUT_DIR, keep_names=keep_files)
========
        "figure6_outdoor_temperature_effect.png",
        "external_temperature_model_summary.txt",
        "figure_summary_one_graph.png",
        "literature_context_comparison.png",
    }
    reset_output_dir(FIG_DIR, keep_names=keep_files)
    RESULTS_DIR.mkdir(exist_ok=True)
>>>>>>>> 509b85d (Reorganize analysis pipeline, regenerate outputs, and clean repo structure):scripts/core/make_figures.py

    df = load_dataset(DATA_FILE)
    models = fit_models(df)
    m_atm = models["atmospheric"]
    m_diurnal = models["diurnal"]

    fig_metrics = make_figures(df, models)

    corr = correlation_table(df)
    corr.to_csv(RESULTS_DIR / "correlation_table.csv", index=False)

    session_table = session_barometric_table(df)
    session_table.to_csv(RESULTS_DIR / "session_summary.csv", index=False)

    coef_table = model_coefficients_table(models)
    coef_table.to_csv(RESULTS_DIR / "model_coefficients.csv", index=False)

    resid_lb = acorr_ljungbox(m_diurnal.resid, lags=[1, 6, 12], return_df=True)
    resid_lb = resid_lb.rename_axis("lag").reset_index()
    resid_lb.to_csv(RESULTS_DIR / "residual_ljungbox.csv", index=False)

    with open(RESULTS_DIR / "regression_summary.txt", "w", encoding="utf-8") as f:
        f.write("PRESSURE-ONLY MODEL (log rate, session fixed effects, HAC SE)\n")
        f.write(models["pressure_only"].summary().as_text())
        f.write("\n\nATMOSPHERIC MODEL (pressure + temperature, session fixed effects, HAC SE)\n")
        f.write(m_atm.summary().as_text())
        f.write("\n\nDIURNAL MODEL (atmospheric + sin/cos 24h, session fixed effects, HAC SE)\n")
        f.write(m_diurnal.summary().as_text())
        f.write("\n\nPOISSON ROBUSTNESS MODEL (counts, log link, HC3 SE)\n")
        f.write(models["poisson_diurnal"].summary().as_text())

    beta = -float(m_atm.params["dP"])
    beta_ci = m_atm.conf_int().loc["dP"]
    beta_ci_low = -float(beta_ci[1])
    beta_ci_high = -float(beta_ci[0])

    diurnal_joint_p = float(m_diurnal.f_test("sin24 = 0, cos24 = 0").pvalue)
    label_map = session_label_map(df)
    run_labels = [label_map[int(x)] for x in sorted(df["session"].unique())]

    diurnal_is_significant = diurnal_joint_p < 0.05

    with open(RESULTS_DIR / "paper_analysis_summary.txt", "w", encoding="utf-8") as f:
        f.write("Muon Atmospheric and Diurnal Analysis Summary\n")
        f.write("===========================================\n")
        f.write(f"N bins (10-minute): {len(df)}\n")
        f.write(f"Runs included: {', '.join(run_labels)}\n")
        run_ids = sorted(int(x) for x in df["run_number"].dropna().unique())
        f.write(f"Run IDs included: {', '.join(str(x) for x in run_ids)}\n")
        f.write(f"UTC span: {df.index.min()} to {df.index.max()}\n")
        f.write(f"Mean rate: {df['rate_cpm'].mean():.4f} counts/min\n")
        f.write(
            f"Pressure range: {df['pressure_hPa'].min():.2f} to {df['pressure_hPa'].max():.2f} hPa\n"
        )
        f.write(f"Temperature range: {df['temp_C'].min():.2f} to {df['temp_C'].max():.2f} C\n\n")

        f.write("Primary atmospheric result:\n")
        f.write(
            f"  Barometric coefficient beta = {100.0 * beta:.4f} %/hPa "
            f"(95% CI {100.0 * beta_ci_low:.4f} to {100.0 * beta_ci_high:.4f}, "
            f"p={m_atm.pvalues['dP']:.3g}).\n"
        )
        f.write(
            f"  Temperature coefficient p-value = {m_atm.pvalues['dT']:.3g} "
            "(not significant if p>0.05).\n"
        )
        f.write(f"  Atmospheric model R^2 = {m_atm.rsquared:.4f}.\n\n")

        f.write("Diurnal result after atmospheric correction:\n")
        f.write(f"  Joint test p-value for 24h harmonic = {diurnal_joint_p:.3g}.\n")
        f.write(
            f"  Harmonic amplitude = {fig_metrics['diurnal_amp_cpm']:.4f} counts/min "
            f"({fig_metrics['diurnal_amp_pct']:.4f} % of mean).\n"
        )
        f.write(f"  Peak phase (local time) = {fig_metrics['diurnal_peak_local_hour']:.2f} h.\n")
        f.write(
            f"  Single-bin Poisson 1-sigma floor (10-min) = {fig_metrics['poisson_floor_pct_10min']:.4f} %, "
            f"amplitude/floor = {fig_metrics['amp_vs_poisson_floor']:.3f}.\n\n"
        )
        if fig_metrics["median_hourly_sem_pct"] > fig_metrics["diurnal_amp_pct"]:
            f.write(
                f"  Median hourly-fold SEM = {fig_metrics['median_hourly_sem_pct']:.4f} % "
                f"(max {fig_metrics['max_hourly_sem_pct']:.4f} %), above the fitted diurnal amplitude.\n\n"
            )
        else:
            f.write(
                f"  Median hourly-fold SEM = {fig_metrics['median_hourly_sem_pct']:.4f} % "
                f"(max {fig_metrics['max_hourly_sem_pct']:.4f} %).\n\n"
            )

        f.write("Interpretation for paper:\n")
        f.write("  Pressure is the dominant and statistically significant atmospheric predictor.\n")
        f.write("  Temperature does not provide a statistically significant additional effect in this dataset.\n")
        if diurnal_is_significant:
            f.write("  A 24-hour diurnal signal is statistically detected after atmospheric correction.\n")
            f.write("  The fitted amplitude remains small, so practical effect size is modest.\n")
        else:
            f.write("  A 24-hour diurnal signal is not statistically resolved after atmospheric correction.\n")

        if not corr.empty:
            top = corr.iloc[0]
            f.write("\nTop raw correlation with count rate:\n")
            f.write(
                f"  {top['predictor']}: r={top['pearson_r']:.4f}, "
                f"R^2={top['r_squared']:.4f}, p={top['p_value']:.3g}.\n"
            )

    print("Done.")
    print(f"Figures saved to: {FIG_DIR.resolve()}")
    print(f"Tables and summaries saved to: {RESULTS_DIR.resolve()}")
    print(f"beta (atmospheric model) = {100.0 * beta:.4f} %/hPa")
    print(f"Diurnal joint p-value = {diurnal_joint_p:.4g}")


if __name__ == "__main__":
    main()
