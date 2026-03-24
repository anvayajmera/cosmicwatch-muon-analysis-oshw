from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[2]
OUT_FILE = ROOT_DIR / "clean_muon_dataset.csv"
FIGURES_DIR = ROOT_DIR / "figures"
REPORT_FILE = FIGURES_DIR / "session_ingest_report.csv"

RESAMPLE_WINDOW = "10min"
CLOCK_JUMP_THRESHOLD_S = 120.0
CLOCK_JUMP_SEARCH_ROWS = 300


@dataclass
class SessionPaths:
    session: int
    directory: Path
    run_date: str | None
    coincidence_file: Path
    master_file: Path | None
    noncoincidence_file: Path | None
    env_file: Path
    system_file: Path
    run_number: int = 0
    run_label: str = ""


def parse_utc_mixed(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, utc=True, errors="coerce", format="mixed")


def discover_session_paths(base_dir: Path) -> list[SessionPaths]:
    out: list[SessionPaths] = []
    data_root = base_dir / "Data"
    data_runs = sorted(data_root.glob("*_*")) if data_root.exists() else []

    for directory in data_runs:
        if not directory.is_dir():
            continue

        match = re.fullmatch(r"(\d+)_(\d{4}-\d{2}-\d{2})", directory.name)
        if not match:
            continue

        session = int(match.group(1))
        run_date = match.group(2)

        def resolve_required(name: str) -> Path:
            target = directory / f"{name}.csv"
            if not target.exists():
                raise FileNotFoundError(f"Missing {name}.csv in {directory}")
            return target

        def resolve_optional(name: str) -> Path | None:
            target = directory / f"{name}.csv"
            return target if target.exists() else None

        try:
            out.append(
                SessionPaths(
                    session=session,
                    directory=directory,
                    run_date=run_date,
                    coincidence_file=resolve_required("cosmicwatch_coincidence"),
                    master_file=resolve_optional("cosmicwatch_master"),
                    noncoincidence_file=resolve_optional("cosmicwatch_noncoincidence"),
                    env_file=resolve_required("env_60s"),
                    system_file=resolve_required("system_metrics"),
                )
            )
        except FileNotFoundError as exc:
            print(f"Skipping {directory.name}: {exc}")

    if not out:
        for directory in sorted(base_dir.glob("session *")):
            if not directory.is_dir():
                continue

            match = re.fullmatch(r"session\s+(\d+)", directory.name)
            if not match:
                continue

            session = int(match.group(1))

            def resolve_file(prefix: str) -> Path:
                preferred = directory / f"{prefix}{session}.csv"
                if preferred.exists():
                    return preferred
                candidates = sorted(directory.glob(f"{prefix}*.csv"))
                if candidates:
                    return candidates[0]
                raise FileNotFoundError(f"Missing {prefix}*.csv in {directory}")

            def resolve_optional(prefix: str) -> Path | None:
                preferred = directory / f"{prefix}{session}.csv"
                if preferred.exists():
                    return preferred
                candidates = sorted(directory.glob(f"{prefix}*.csv"))
                return candidates[0] if candidates else None

            try:
                out.append(
                    SessionPaths(
                        session=session,
                        directory=directory,
                        run_date=None,
                        coincidence_file=resolve_file("cosmicwatch_coincidence"),
                        master_file=resolve_optional("cosmicwatch_master"),
                        noncoincidence_file=resolve_optional("cosmicwatch_noncoincidence"),
                        env_file=resolve_file("env_60s"),
                        system_file=resolve_file("system_metrics"),
                    )
                )
            except FileNotFoundError as exc:
                print(f"Skipping {directory.name}: {exc}")

    out.sort(key=lambda x: (x.run_date or "", x.directory.name))
    return out


def apply_startup_clock_jump_fix(
    cw: pd.DataFrame,
    session: int,
    threshold_s: float = CLOCK_JUMP_THRESHOLD_S,
    max_startup_row: int = CLOCK_JUMP_SEARCH_ROWS,
) -> tuple[pd.DataFrame, dict | None]:
    if "runtime_s" not in cw.columns:
        return cw, None

    cw = cw.sort_values("ts_utc").reset_index(drop=True).copy()
    runtime = pd.to_numeric(cw["runtime_s"], errors="coerce")
    dt_wall = cw["ts_utc"].diff().dt.total_seconds()
    dt_runtime = runtime.diff()
    jump_delta = dt_wall - dt_runtime

    candidates = jump_delta[(jump_delta > threshold_s) & (cw.index <= max_startup_row)]
    if candidates.empty:
        return cw, None

    jump_idx = int(candidates.index[0])
    if jump_idx <= 0:
        return cw, None

    shift_s = float(candidates.iloc[0])
    cw.loc[: jump_idx - 1, "ts_utc"] = cw.loc[: jump_idx - 1, "ts_utc"] + pd.to_timedelta(shift_s, unit="s")
    cw = cw.sort_values("ts_utc").reset_index(drop=True)

    runtime_after = pd.to_numeric(cw["runtime_s"], errors="coerce")
    residual = cw["ts_utc"].diff().dt.total_seconds() - runtime_after.diff()
    residual_large = int((residual.abs() > 10.0).sum())

    info = {
        "session": session,
        "jump_idx": jump_idx,
        "jump_shift_s": round(shift_s, 6),
        "rows_shifted": jump_idx,
        "residual_large_after_fix": residual_large,
    }
    return cw, info


def count_csv_rows(path: Path | None) -> int | None:
    if path is None or not path.exists():
        return None

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return max(sum(1 for _ in f) - 1, 0)


def load_session(paths: SessionPaths) -> tuple[pd.DataFrame, dict]:
    cw = pd.read_csv(paths.coincidence_file)
    env = pd.read_csv(paths.env_file)
    sys = pd.read_csv(paths.system_file)

    report = {
        "session": paths.session,
        "run_number": paths.run_number,
        "run_label": paths.run_label,
        "run_date": paths.run_date if paths.run_date else "",
        "cw_rows_raw": len(cw),
        "env_rows_raw": len(env),
        "sys_rows_raw": len(sys),
    }
    master_rows_raw = count_csv_rows(paths.master_file)
    noncoinc_rows_raw = count_csv_rows(paths.noncoincidence_file)
    report["master_rows_raw"] = master_rows_raw if master_rows_raw is not None else -1
    report["noncoinc_rows_raw"] = noncoinc_rows_raw if noncoinc_rows_raw is not None else -1
    report["coincidence_fraction_of_master"] = (
        round(report["cw_rows_raw"] / master_rows_raw, 6) if master_rows_raw and master_rows_raw > 0 else None
    )

    cw["ts_utc"] = parse_utc_mixed(cw["ts_utc"])
    env["window_start_utc"] = parse_utc_mixed(env["window_start_utc"])
    env["window_end_utc"] = parse_utc_mixed(env["window_end_utc"])
    sys["ts_utc"] = parse_utc_mixed(sys["ts_utc"])

    report["cw_invalid_ts"] = int(cw["ts_utc"].isna().sum())
    report["env_invalid_start"] = int(env["window_start_utc"].isna().sum())
    report["env_invalid_end"] = int(env["window_end_utc"].isna().sum())
    report["sys_invalid_ts"] = int(sys["ts_utc"].isna().sum())
    if "cpu_tempC" in sys.columns:
        cpu = pd.to_numeric(sys["cpu_tempC"], errors="coerce")
        report["cpu_tempC_min"] = round(float(cpu.min()), 3) if cpu.notna().any() else None
        report["cpu_tempC_max"] = round(float(cpu.max()), 3) if cpu.notna().any() else None
        report["cpu_tempC_mean"] = round(float(cpu.mean()), 3) if cpu.notna().any() else None
    else:
        report["cpu_tempC_min"] = None
        report["cpu_tempC_max"] = None
        report["cpu_tempC_mean"] = None

    if "throttled" in sys.columns:
        throttled_series = sys["throttled"].astype(str).str.strip()
        valid = throttled_series.ne("") & throttled_series.ne("nan")
        nonzero = valid & throttled_series.ne("throttled=0x0")
        report["sys_throttled_nonzero_rows"] = int(nonzero.sum())
    else:
        report["sys_throttled_nonzero_rows"] = None

    cw = cw.dropna(subset=["ts_utc"]).copy()
    env = env.dropna(subset=["window_start_utc", "window_end_utc"]).copy()
    sys = sys.dropna(subset=["ts_utc"]).copy()

    env = env[env["window_end_utc"] > env["window_start_utc"]].copy()
    report["env_nonpositive_windows_removed"] = report["env_rows_raw"] - len(env)

    cw, jump_info = apply_startup_clock_jump_fix(cw, paths.session)
    report["startup_clock_jump_fixed"] = int(jump_info is not None)
    report["startup_clock_jump_shift_s"] = jump_info["jump_shift_s"] if jump_info else 0.0
    report["startup_clock_rows_shifted"] = jump_info["rows_shifted"] if jump_info else 0

    cw = cw.sort_values("ts_utc").copy()
    env = env.sort_values("window_start_utc").copy()
    sys = sys.sort_values("ts_utc").copy()

    start = max(cw["ts_utc"].min(), env["window_start_utc"].min(), sys["ts_utc"].min())
    end = min(cw["ts_utc"].max(), env["window_end_utc"].max(), sys["ts_utc"].max())
    if end <= start:
        raise RuntimeError(f"Session {paths.session} has no overlap window after timestamp cleanup.")

    report["overlap_start_utc"] = start
    report["overlap_end_utc"] = end
    report["overlap_hours"] = round((end - start).total_seconds() / 3600.0, 3)

    cw = cw[(cw["ts_utc"] >= start) & (cw["ts_utc"] <= end)].copy().set_index("ts_utc")
    env = env[(env["window_start_utc"] >= start) & (env["window_start_utc"] <= end)].copy().set_index("window_start_utc")
    sys = sys[(sys["ts_utc"] >= start) & (sys["ts_utc"] <= end)].copy().set_index("ts_utc")

    rate = cw.resample(RESAMPLE_WINDOW).size().rename("muon_counts")
    report["rows_resampled_raw"] = len(rate)
    if len(rate) > 2:
        rate = rate.iloc[1:-1]
    report["rows_resampled_trimmed"] = len(rate)

    env_10 = env.select_dtypes(include="number").resample(RESAMPLE_WINDOW).mean()
    sys_10 = sys.select_dtypes(include="number").resample(RESAMPLE_WINDOW).mean()

    out = pd.concat([rate, env_10, sys_10], axis=1).dropna().copy()
    out["session"] = paths.session
    out["run_number"] = paths.run_number
    out["run_label"] = paths.run_label
    out["run_date"] = paths.run_date if paths.run_date else ""
    out["rate_cpm"] = out["muon_counts"] / 10.0

    report["rows_clean_10min"] = len(out)
    report["coverage_fraction_clean"] = (
        round(report["rows_clean_10min"] / report["rows_resampled_trimmed"], 6)
        if report["rows_resampled_trimmed"] > 0
        else 0.0
    )
    report["mean_rate_cpm"] = round(float(out["rate_cpm"].mean()), 4) if len(out) else 0.0
    return out, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build clean muon dataset from all session folders.")
    parser.add_argument(
        "--sessions",
        nargs="+",
        type=int,
        default=None,
        help="Optional list of session numbers to include.",
    )
    parser.add_argument(
        "--all-sessions",
        action="store_true",
        help="Include all discovered sessions. If omitted, only the newest session is used by default.",
    )
    return parser.parse_args()


def main() -> None:
    print("Starting analysis...")
    args = parse_args()

    sessions = discover_session_paths(ROOT_DIR)
    if args.sessions is not None:
        requested = set(args.sessions)
        sessions = [s for s in sessions if s.session in requested]
    elif not args.all_sessions and sessions:
        sessions = [sessions[-1]]

    if not sessions:
        raise RuntimeError("No valid session folders found.")

    for i, session_paths in enumerate(sessions, start=1):
        session_paths.run_number = i
        session_paths.run_label = f"Run {i} ({session_paths.run_date})" if session_paths.run_date else f"Run {i}"

    print(f"Using runs: {', '.join(s.run_label for s in sessions)}")

    clean_parts: list[pd.DataFrame] = []
    reports: list[dict] = []

    for paths in sessions:
        part, report = load_session(paths)
        clean_parts.append(part)
        reports.append(report)

    data = pd.concat(clean_parts).sort_index()
    data.index.name = "ts_utc"
    data.to_csv(OUT_FILE, index_label="ts_utc")

    FIGURES_DIR.mkdir(exist_ok=True)
    pd.DataFrame(reports).sort_values(["run_number", "session"]).to_csv(REPORT_FILE, index=False)

    print("Done.")
    for report in sorted(reports, key=lambda x: (x["run_number"], x["session"])):
        print(
            f"{report['run_label']} [session {report['session']}]:",
            f"{report['rows_clean_10min']} bins,",
            f"mean {report['mean_rate_cpm']:.3f} cpm,",
            f"invalid cw ts {report['cw_invalid_ts']},",
            f"startup jump fixed {bool(report['startup_clock_jump_fixed'])},",
            f"coinc/master {report['coincidence_fraction_of_master'] if report['coincidence_fraction_of_master'] is not None else 'n/a'}",
        )
    print(f"Total rows: {len(data)}")
    print(f"Saved: {OUT_FILE.name}")
    print(f"Ingest report: {REPORT_FILE}")


if __name__ == "__main__":
    main()
