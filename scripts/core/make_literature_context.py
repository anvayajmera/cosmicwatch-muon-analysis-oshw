from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_FIG_DIR = PROJECT_ROOT / "figures"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate literature-comparison context outputs.")
    parser.add_argument("--model-coefs", default=str(DEFAULT_RESULTS_DIR / "model_coefficients.csv"), help="Path to model coefficients CSV.")
    parser.add_argument("--summary-file", default=str(DEFAULT_RESULTS_DIR / "paper_analysis_summary.txt"), help="Path to analysis summary text.")
    parser.add_argument("--results-dir", default=str(DEFAULT_RESULTS_DIR), help="Output directory for summary text.")
    parser.add_argument("--figure-dir", default=str(DEFAULT_FIG_DIR), help="Output directory for optional comparison figure.")
    parser.add_argument(
        "--with-figure",
        action="store_true",
        help="Also generate literature_context_comparison.png (disabled by default to keep final figure set compact).",
    )
    return parser.parse_args()


def extract_current_metrics(model_coefs: Path, summary_file: Path) -> tuple[float, float, float, float, int]:
    coef = pd.read_csv(model_coefs)
    atm = coef[(coef["model"] == "atmospheric") & (coef["term"] == "dP")]
    if atm.empty:
        raise RuntimeError("Could not find atmospheric dP coefficient in model_coefficients.csv")
    beta_pct_per_hpa = -100.0 * float(atm.iloc[0]["coef"])
    p_beta = float(atm.iloc[0]["p_value"])

    di = coef[(coef["model"] == "diurnal") & (coef["term"].isin(["sin24", "cos24"]))].set_index("term")
    if len(di) != 2:
        raise RuntimeError("Could not find diurnal sin24/cos24 coefficients in model_coefficients.csv")
    a = float(di.loc["sin24", "coef"])
    b = float(di.loc["cos24", "coef"])
    amp_pct = float(np.sqrt(a * a + b * b) * 100.0)

    p_joint = np.nan
    n_bins = 0
    if summary_file.exists():
        txt = summary_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in txt:
            if "Joint test p-value for 24h harmonic" in line:
                try:
                    p_joint = float(line.split("=")[-1].strip().rstrip("."))
                except ValueError:
                    pass
                break
        for line in txt:
            if line.startswith("N bins (10-minute):"):
                try:
                    n_bins = int(line.split(":")[-1].strip().replace(",", ""))
                except ValueError:
                    pass
                break
    return beta_pct_per_hpa, amp_pct, p_joint, p_beta, n_bins


def make_figure(beta_now: float, amp_now: float, p_joint: float, p_beta: float, n_bins: int, out_dir: Path) -> None:
    import matplotlib.pyplot as plt

    # Literature anchors from primary sources listed in LITERATURE_CONTEXT.md
    beta_refs = np.array([0.067, 0.168, 0.21])  # |beta| %/hPa
    beta_lo = float(beta_refs.min())
    beta_hi = float(beta_refs.max())

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(14.8, 5.8), dpi=280, constrained_layout=True)

    # Panel A: beta in published range
    ax = axes[0]
    ax.hlines(1, beta_lo, beta_hi, color="#4c78a8", linewidth=8, alpha=0.35, label="Published range")
    ax.plot(abs(beta_now), 1, "o", color="#e45756", markersize=9, label="This work")
    ax.set_ylim(0.4, 1.6)
    ax.set_yticks([1])
    ax.set_yticklabels(["|β| (%/hPa)"])
    ax.set_xlabel("Coefficient Magnitude")
    ax.set_title("Pressure Sensitivity Benchmark")
    ax.text(abs(beta_now), 1.08, f"{abs(beta_now):.3f}", ha="center", fontsize=9)
    ax.legend(loc="lower right", fontsize=8)

    # Panel B: significance strength (-log10 p)
    ax = axes[1]
    pvals = [max(p_beta, 1e-16), max(p_joint, 1e-16)]
    labels = ["Pressure term", "24h diurnal term"]
    sig = -np.log10(pvals)
    bars = ax.bar(labels, sig, color=["#4c78a8", "#72b7b2"], alpha=0.9)
    ax.axhline(-np.log10(0.05), color="black", linestyle="--", linewidth=1.0, label="p = 0.05")
    ax.set_ylabel("-log10(p)")
    ax.set_title("Statistical Detection Strength")
    for b, p in zip(bars, pvals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.1, f"p={p:.2g}", ha="center", fontsize=8)
    ax.legend(loc="upper right", fontsize=8)

    # Panel C: dataset scale and amplitude
    ax = axes[2]
    cats = ["N bins (10-min)", "24h amplitude (%)"]
    vals = [float(n_bins), float(amp_now)]
    ax.bar(cats, vals, color=["#54a24b", "#f58518"], alpha=0.9)
    ax.set_title("Dataset Scale and Signal Size")
    ax.set_ylabel("Value")
    ax.tick_params(axis="x", labelrotation=12)
    ax.text(0, vals[0] * 1.01, f"{int(vals[0])}", ha="center", fontsize=8)
    ax.text(1, vals[1] * 1.07 if vals[1] > 0 else 0.05, f"{vals[1]:.3f}%", ha="center", fontsize=8)

    fig.suptitle("Low-Cost Detector Performance in Literature Context", fontsize=13)
    fig.savefig(out_dir / "literature_context_comparison.png", bbox_inches="tight")
    plt.close(fig)


def write_summary(beta_now: float, amp_now: float, p_joint: float, p_beta: float, n_bins: int, out_dir: Path) -> None:
    out = out_dir / "literature_context_summary.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write("Literature Context Summary\n")
        f.write("=========================\n")
        f.write(f"This work beta: {beta_now:.4f} %/hPa\n")
        f.write(f"This work pressure-term p-value: {p_beta:.5g}\n")
        if np.isfinite(p_joint):
            f.write(f"This work diurnal joint p-value: {p_joint:.5g}\n")
        f.write(f"This work diurnal amplitude: {amp_now:.4f} %\n\n")
        f.write(f"This work N bins (10-minute): {n_bins}\n\n")
        f.write("Reference anchors used in comparison figure:\n")
        f.write("- KACST detector (Adv. Space Res. 2018): beta ~ -0.067 +/- 0.008 %/hPa\n")
        f.write("- Mexico City scintillator pair (arXiv:2403.13978): beta ~ -0.21 %/hPa\n")
        f.write("- Applied Sciences 2021 detector: beta_TOP ~ -0.168 %/hPa\n")
        f.write("- Matsushiro 1991 (Compton-Getting solar diurnal, E-W): amp ~ 0.030 +/- 0.007 %\n")
        f.write("- Matsushiro 2010 (sidereal average anisotropy): amp ~ 0.034 +/- 0.003 %\n")
        f.write("\nRatio comparison:\n")
        f.write(f"- |beta| / 0.067 (KACST 2018) = {beta_now / 0.067:.2f}x\n")
        f.write(f"- |beta| / 0.21 (Mexico City 2024) = {beta_now / 0.21:.2f}x\n")
        f.write(f"- |beta| / 0.168 (Appl. Sci. 2021) = {beta_now / 0.168:.2f}x\n")
        f.write(f"- amp / 0.030 (Matsushiro 1991 solar E-W) = {amp_now / 0.030:.1f}x\n")
        f.write(f"- amp / 0.034 (Matsushiro 2010 sidereal) = {amp_now / 0.034:.1f}x\n")
        f.write("\nInterpretive note:\n")
        f.write(
            "This detector reproduces a literature-consistent pressure response and detects a statistically significant 24-hour residual modulation. Because this is a compact non-directional setup, the 24-hour amplitude is best interpreted as residual daily modulation strength at this site/instrument configuration.\n"
        )

    print(f"Saved: {out}")


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results_dir)
    figure_dir = Path(args.figure_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    beta_now, amp_now, p_joint, p_beta, n_bins = extract_current_metrics(Path(args.model_coefs), Path(args.summary_file))
    if args.with_figure:
        make_figure(beta_now, amp_now, p_joint, p_beta, n_bins, figure_dir)
    write_summary(beta_now, amp_now, p_joint, p_beta, n_bins, results_dir)


if __name__ == "__main__":
    main()
