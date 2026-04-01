from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import requests


IEM_ASOS_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_FILE = PROJECT_ROOT / "results" / "clean_muon_dataset.csv"
DEFAULT_OUT_DIR = PROJECT_ROOT / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch KSMQ ASOS data and align to 10-minute muon bins.")
    parser.add_argument("--data-file", default=str(DEFAULT_DATA_FILE), help="Path to clean muon dataset.")
    parser.add_argument("--station", default="KSMQ", help="ASOS station code (default: KSMQ).")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory.")
    return parser.parse_args()


def fetch_asos(station: str, start_utc: pd.Timestamp, end_utc: pd.Timestamp) -> pd.DataFrame:
    params = [
        ("station", station.upper()),
        ("data", "tmpf"),
        ("data", "mslp"),
        ("year1", str(start_utc.year)),
        ("month1", str(start_utc.month)),
        ("day1", str(start_utc.day)),
        ("year2", str(end_utc.year)),
        ("month2", str(end_utc.month)),
        ("day2", str(end_utc.day)),
        ("tz", "Etc/UTC"),
        ("format", "onlycomma"),
        ("latlon", "no"),
        ("elev", "no"),
        ("missing", "M"),
        ("trace", "T"),
        ("direct", "no"),
        ("report_type", "1"),
        ("report_type", "2"),
        ("report_type", "3"),
    ]
    resp = requests.get(IEM_ASOS_URL, params=params, timeout=45)
    resp.raise_for_status()

    lines = resp.text.strip().splitlines()
    if len(lines) <= 1:
        raise RuntimeError("ASOS request returned no data rows.")

    rows: list[dict] = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < 4:
            continue
        valid = pd.to_datetime(parts[1], utc=True, errors="coerce", format="%Y-%m-%d %H:%M")
        if pd.isna(valid):
            continue
        tmpf = np.nan if parts[2] == "M" else float(parts[2])
        mslp = np.nan if parts[3] == "M" else float(parts[3])  # hPa
        rows.append({"ts_utc": valid, "tmpf": tmpf, "mslp_hPa": mslp})

    df = pd.DataFrame(rows).drop_duplicates(subset=["ts_utc"]).sort_values("ts_utc")
    if df.empty:
        raise RuntimeError("Parsed ASOS data is empty after cleanup.")

    df["smq_tempC"] = (df["tmpf"] - 32.0) * (5.0 / 9.0)
    return df[["ts_utc", "smq_tempC", "mslp_hPa"]]


def align_to_muon_bins(muon: pd.DataFrame, station: pd.DataFrame) -> pd.DataFrame:
    target = pd.DatetimeIndex(muon["ts_utc"].sort_values().unique())
    st = station.set_index("ts_utc").sort_index()

    expanded = st.reindex(st.index.union(target)).sort_index()
    interp = expanded.interpolate(method="time", limit_direction="both")
    aligned = interp.reindex(target).reset_index().rename(columns={"index": "ts_utc"})
    aligned = aligned.rename(
        columns={"smq_tempC": "smq_tempC_interp", "mslp_hPa": "smq_mslp_hPa_interp"}
    )
    return aligned


def save_outputs(muon: pd.DataFrame, aligned: pd.DataFrame, out_dir: Path) -> None:
    merged = muon.merge(aligned, on="ts_utc", how="left")
    merged["bmp_pressure_hPa"] = merged["bmp_pressurePa_mean"] / 100.0
    merged["temp_diff_C"] = merged["bmp_tempC_mean"] - merged["smq_tempC_interp"]
    merged["pressure_diff_hPa"] = merged["bmp_pressure_hPa"] - merged["smq_mslp_hPa_interp"]

    compare_cols = [
        "ts_utc",
        "bmp_tempC_mean",
        "bmp_pressurePa_mean",
        "bmp_pressure_hPa",
        "smq_tempC_interp",
        "smq_mslp_hPa_interp",
        "temp_diff_C",
        "pressure_diff_hPa",
        "session",
        "run_label",
        "run_date",
    ]
    compare = merged[compare_cols].copy()

    outdoor = merged[["ts_utc", "smq_tempC_interp", "smq_mslp_hPa_interp", "session", "run_label", "run_date"]].copy()
    outdoor = outdoor.rename(columns={"smq_tempC_interp": "outdoor_tempC", "smq_mslp_hPa_interp": "outdoor_mslp_hPa"})

    compare_file = out_dir / "station_smq_10min_temperature_pressure_comparison.csv"
    outdoor_file = out_dir / "temperature_outdoor_346_cynthia_lane_10min.csv"
    compare.to_csv(compare_file, index=False)
    outdoor.to_csv(outdoor_file, index=False)

    temp_mad = float(np.nanmean(np.abs(compare["temp_diff_C"])))
    pressure_mad = float(np.nanmean(np.abs(compare["pressure_diff_hPa"])))
    temp_corr = float(compare[["bmp_tempC_mean", "smq_tempC_interp"]].corr().iloc[0, 1])
    pressure_corr = float(compare[["bmp_pressure_hPa", "smq_mslp_hPa_interp"]].corr().iloc[0, 1])

    with open(out_dir / "station_validation_summary.txt", "w", encoding="utf-8") as f:
        f.write("Station Validation Summary (KSMQ vs Onboard BMP280)\n")
        f.write("===================================================\n")
        f.write(f"N aligned bins: {len(compare)}\n")
        f.write(f"UTC span: {compare['ts_utc'].min()} to {compare['ts_utc'].max()}\n")
        f.write(f"Pressure MAD (BMP - station): {pressure_mad:.3f} hPa\n")
        f.write(f"Temperature MAD (BMP - station): {temp_mad:.3f} C\n")
        f.write(f"Pressure correlation: {pressure_corr:.4f}\n")
        f.write(f"Temperature correlation: {temp_corr:.4f}\n")

    print(f"Saved: {compare_file}")
    print(f"Saved: {outdoor_file}")
    print(f"Saved: {out_dir / 'station_validation_summary.txt'}")
    print(f"Pressure MAD: {pressure_mad:.3f} hPa")
    print(f"Temperature MAD: {temp_mad:.3f} C")


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    muon = pd.read_csv(args.data_file)
    muon["ts_utc"] = pd.to_datetime(muon["ts_utc"], utc=True, errors="coerce", format="mixed")
    muon = muon.dropna(subset=["ts_utc", "bmp_tempC_mean", "bmp_pressurePa_mean"]).copy()
    muon = muon.sort_values("ts_utc")

    start = muon["ts_utc"].min().floor("D")
    end = muon["ts_utc"].max().ceil("D")
    station = fetch_asos(args.station, start, end)
    aligned = align_to_muon_bins(muon, station)
    save_outputs(muon, aligned, out_dir)


if __name__ == "__main__":
    main()
