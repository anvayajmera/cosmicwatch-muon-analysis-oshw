#!/usr/bin/env python3

import argparse
import csv
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import serial

# I2C sensor libs (optional if disabled / missing)
import board
import busio
import adafruit_bmp280
import adafruit_bno055

try:
    import fcntl  # Linux-only, present on Raspberry Pi OS
except Exception:
    fcntl = None


STOP = False


# -----------------------------
# Basic utilities
# -----------------------------
def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def mkdirp(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def fsync_file(f) -> None:
    try:
        f.flush()
        os.fsync(f.fileno())
    except Exception:
        pass


def safe_write_text(path: str, text: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def open_linebuffered(path: str):
    return open(path, "a", buffering=1, encoding="utf-8")


def get_cpu_temp_c() -> float:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r", encoding="utf-8") as f:
            return float(f.read().strip()) / 1000.0
    except Exception:
        return float("nan")


def get_throttled():
    cmd = shutil.which("vcgencmd")
    if not cmd:
        return ""
    try:
        p = subprocess.run([cmd, "get_throttled"], capture_output=True, text=True, timeout=2)
        return (p.stdout or "").strip()
    except Exception:
        return ""


def read_boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id", "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def wait_for_path(path: str, max_wait_s: int) -> bool:
    start = time.time()
    while not STOP and (time.time() - start) < max_wait_s:
        if os.path.exists(path):
            return True
        time.sleep(0.2)
    return False


def wait_for_ntp_sync(max_wait_s: int) -> bool:
    start = time.time()
    while not STOP and (time.time() - start) < max_wait_s:
        try:
            p = subprocess.run(
                ["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if (p.stdout or "").strip().lower() == "yes":
                return True
        except Exception:
            return False
        time.sleep(1)
    return False


def handle_sig(*_):
    global STOP
    STOP = True


# -----------------------------
# Locking (prevents double-run)
# -----------------------------
def acquire_lock(lock_path: str, log_f=None):
    """
    Creates/opens lock file and grabs an exclusive lock.
    If another instance holds it, exit immediately.
    """
    mkdirp(os.path.dirname(lock_path) or ".")
    f = open(lock_path, "w", encoding="utf-8")
    if fcntl is None:
        # Fallback: best-effort only
        try:
            f.write(str(os.getpid()))
            f.flush()
        except Exception:
            pass
        return f

    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        msg = f"{iso_utc_now()} ERROR another_logger_instance_running lock={lock_path}\n"
        if log_f:
            log_f.write(msg)
            fsync_file(log_f)
        print("[ERROR] Another logger instance is already running (lock busy). Stop it first.")
        sys.exit(10)

    try:
        f.write(str(os.getpid()))
        f.flush()
        os.fsync(f.fileno())
    except Exception:
        pass
    return f


# -----------------------------
# Run folder management
# -----------------------------
def next_run_folder(base_outdir: str):
    mkdirp(base_outdir)
    counter_path = os.path.join(base_outdir, "run_counter.txt")
    try:
        with open(counter_path, "r", encoding="utf-8") as f:
            n = int(f.read().strip())
    except Exception:
        n = 0
    n += 1
    safe_write_text(counter_path, f"{n}\n")

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder_name = f"{n:04d}_{date_str}"
    run_folder = os.path.join(base_outdir, folder_name)
    mkdirp(run_folder)
    mkdirp(os.path.join(run_folder, "photos"))
    return n, run_folder, folder_name


# -----------------------------
# Camera (optional)
# -----------------------------
def camera_command():
    for c in ["rpicam-still", "libcamera-still"]:
        if shutil.which(c):
            return c
    return None


def capture_photo(cam_cmd, out_path, log_f):
    ts = iso_utc_now()
    if not cam_cmd:
        log_f.write(f"{ts},ERROR,no_camera_command_found\n")
        return False

    for attempt in range(1, 6):
        if STOP:
            return False
        try:
            mkdirp(os.path.dirname(out_path))
            p = subprocess.run(
                [cam_cmd, "-n", "-t", "1000", "-o", out_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if p.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                log_f.write(f"{ts},OK,{out_path}\n")
                return True
            log_f.write(
                f"{ts},RETRY{attempt},rc={p.returncode},stderr={repr((p.stderr or '')[-200:])}\n"
            )
        except Exception as e:
            log_f.write(f"{ts},RETRY{attempt},EXC,{repr(e)}\n")
        time.sleep(2 * attempt)

    log_f.write(f"{ts},ERROR,capture_failed,{out_path}\n")
    return False


def photo_loop(run_folder, interval_s, do_immediate, cam_log_f):
    cam_cmd = camera_command()
    photos_dir = os.path.join(run_folder, "photos")

    if do_immediate and not STOP:
        fn = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ.jpg")
        capture_photo(cam_cmd, os.path.join(photos_dir, fn), cam_log_f)
        fsync_file(cam_log_f)

    next_t = time.time() + interval_s
    while not STOP:
        now = time.time()
        if now < next_t:
            time.sleep(min(2.0, next_t - now))
            continue
        next_t += interval_s

        fn = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ.jpg")
        capture_photo(cam_cmd, os.path.join(photos_dir, fn), cam_log_f)
        fsync_file(cam_log_f)


# -----------------------------
# System metrics thread
# -----------------------------
def sys_loop(sys_f, hz):
    period = 1.0 / hz
    next_t = time.time()

    if os.stat(sys_f.name).st_size == 0:
        sys_f.write("ts_utc,cpu_tempC,disk_free_bytes,throttled\n")

    while not STOP:
        now = time.time()
        if now < next_t:
            time.sleep(min(0.5, next_t - now))
            continue
        next_t += period

        ts = iso_utc_now()
        try:
            du = shutil.disk_usage("/")
            sys_f.write(f"{ts},{get_cpu_temp_c():.2f},{du.free},{get_throttled()}\n")
        except Exception as e:
            sys_f.write(f"{ts},ERROR,{repr(e)}\n")


# -----------------------------
# NaN-safe stats helpers
# -----------------------------
def to_float_or_nan(x):
    if x is None:
        return float("nan")
    try:
        fx = float(x)
    except Exception:
        return float("nan")
    if math.isnan(fx) or math.isinf(fx):
        return float("nan")
    return fx


def nanmean(vals):
    good = []
    for v in vals:
        fv = to_float_or_nan(v)
        if not math.isnan(fv):
            good.append(fv)
    if not good:
        return float("nan")
    return sum(good) / len(good)


def mode_int(vals):
    clean = []
    for v in vals:
        if v is None:
            continue
        try:
            iv = int(v)
            clean.append(iv)
        except Exception:
            continue
    if not clean:
        return ""
    counts = {}
    for iv in clean:
        counts[iv] = counts.get(iv, 0) + 1
    # highest count, then smallest value
    return str(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0])


def clamp_or_nan(x, lo, hi):
    fx = to_float_or_nan(x)
    if math.isnan(fx):
        return float("nan")
    if fx < lo or fx > hi:
        return float("nan")
    return fx


# -----------------------------
# Environment aggregation thread
# -----------------------------
def env_aggregate_loop(env_f, bmp, bno, sample_hz, window_s, sea_level_hpa, include_bno: bool, run_log=None):
    period = 1.0 / sample_hz
    next_t = time.time()

    bmp_cols = ["bmp_tempC_mean", "bmp_pressurePa_mean", "bmp_altitudeM_est_mean"]

    bno_mean_cols = []
    bno_tail_cols = []
    if include_bno and bno is not None:
        bno_mean_cols = [
            "euler_heading_deg_mean", "euler_roll_deg_mean", "euler_pitch_deg_mean",
            "quat_w_mean", "quat_x_mean", "quat_y_mean", "quat_z_mean",
            "accel_x_mps2_mean", "accel_y_mps2_mean", "accel_z_mps2_mean",
            "linacc_x_mps2_mean", "linacc_y_mps2_mean", "linacc_z_mps2_mean",
            "gravity_x_mps2_mean", "gravity_y_mps2_mean", "gravity_z_mps2_mean",
            "gyro_x_rads_mean", "gyro_y_rads_mean", "gyro_z_rads_mean",
            "mag_x_uT_mean", "mag_y_uT_mean", "mag_z_uT_mean",
        ]
        bno_tail_cols = ["calib_sys_mode", "calib_gyro_mode", "calib_accel_mode", "calib_mag_mode"]

    header = ["window_start_utc", "window_end_utc", "n_samples"] + bmp_cols + bno_mean_cols + bno_tail_cols
    if os.stat(env_f.name).st_size == 0:
        env_f.write(",".join(header) + "\n")

    win_start = iso_utc_now()
    win_start_t = time.time()

    bmp_temp, bmp_press, bmp_alt = [], [], []

    b = {k: [] for k in bno_mean_cols}
    calib_sys, calib_gyro, calib_accel, calib_mag = [], [], [], []

    while not STOP:
        try:
            now = time.time()
            if now < next_t:
                time.sleep(min(0.2, next_t - now))
                continue
            next_t += period

            if bmp is not None:
                try:
                    bmp.sea_level_pressure = float(sea_level_hpa)
                    tC = clamp_or_nan(bmp.temperature, -30, 80)
                    pPa = clamp_or_nan(bmp.pressure * 100.0, 60000, 115000)
                    alt = to_float_or_nan(getattr(bmp, "altitude", float("nan")))
                    bmp_temp.append(tC)
                    bmp_press.append(pPa)
                    bmp_alt.append(alt)
                except Exception:
                    pass

            if include_bno and bno is not None:
                try:
                    euler = bno.euler
                    quat = bno.quaternion
                    accel = bno.acceleration
                    linacc = bno.linear_acceleration
                    grav = bno.gravity
                    gyro = bno.gyro
                    mag = bno.magnetic
                    calib = bno.calibration_status

                    def f3(tup):
                        if not tup:
                            return (None, None, None)
                        return (tup[0], tup[1], tup[2])

                    def f4(tup):
                        if not tup:
                            return (None, None, None, None)
                        return (tup[0], tup[1], tup[2], tup[3])

                    eh, er, ep = f3(euler)
                    qw, qx, qy, qz = f4(quat)
                    ax, ay, az = f3(accel)
                    lax, lay, laz = f3(linacc)
                    gx, gy, gz = f3(grav)
                    grx, gry, grz = f3(gyro)
                    mx, my, mz = f3(mag)

                    # push
                    b["euler_heading_deg_mean"].append(eh)
                    b["euler_roll_deg_mean"].append(er)
                    b["euler_pitch_deg_mean"].append(ep)

                    b["quat_w_mean"].append(qw)
                    b["quat_x_mean"].append(qx)
                    b["quat_y_mean"].append(qy)
                    b["quat_z_mean"].append(qz)

                    b["accel_x_mps2_mean"].append(ax)
                    b["accel_y_mps2_mean"].append(ay)
                    b["accel_z_mps2_mean"].append(az)

                    b["linacc_x_mps2_mean"].append(lax)
                    b["linacc_y_mps2_mean"].append(lay)
                    b["linacc_z_mps2_mean"].append(laz)

                    b["gravity_x_mps2_mean"].append(gx)
                    b["gravity_y_mps2_mean"].append(gy)
                    b["gravity_z_mps2_mean"].append(gz)

                    b["gyro_x_rads_mean"].append(grx)
                    b["gyro_y_rads_mean"].append(gry)
                    b["gyro_z_rads_mean"].append(grz)

                    b["mag_x_uT_mean"].append(mx)
                    b["mag_y_uT_mean"].append(my)
                    b["mag_z_uT_mean"].append(mz)

                    if calib is not None and len(calib) >= 4:
                        calib_sys.append(calib[0])
                        calib_gyro.append(calib[1])
                        calib_accel.append(calib[2])
                        calib_mag.append(calib[3])

                except Exception:
                    pass

            if (time.time() - win_start_t) >= window_s:
                win_end = iso_utc_now()
                n = len(bmp_temp)

                row = [
                    win_start,
                    win_end,
                    str(n),
                    f"{nanmean(bmp_temp):.4f}",
                    f"{nanmean(bmp_press):.2f}",
                    f"{nanmean(bmp_alt):.4f}",
                ]

                for k in bno_mean_cols:
                    row.append(f"{nanmean(b.get(k, [])):.6f}")

                if bno_tail_cols:
                    row += [mode_int(calib_sys), mode_int(calib_gyro), mode_int(calib_accel), mode_int(calib_mag)]

                env_f.write(",".join(row) + "\n")

                # reset window
                win_start = iso_utc_now()
                win_start_t = time.time()
                bmp_temp.clear()
                bmp_press.clear()
                bmp_alt.clear()
                for k in b:
                    b[k].clear()
                calib_sys.clear()
                calib_gyro.clear()
                calib_accel.clear()
                calib_mag.clear()

        except Exception as e:
            if run_log:
                run_log.write(f"{iso_utc_now()} ENV_THREAD_ERROR {repr(e)}\n")
                fsync_file(run_log)
            time.sleep(1)


# -----------------------------
# CosmicWatch parsing + serial robustness
# -----------------------------
def parse_cw_line(line: str):
    """
    Returns tuple(event, runtime_s, flag, adc, sipm_mv, dead_s, name) or None
    Rejects corrupt lines via sanity checks.
    """
    parts = line.split("\t")
    if len(parts) < 6:
        return None

    try:
        event = int(parts[0])
        runtime_s = float(parts[1])
        flag = int(parts[2])
        adc = int(parts[3])
        sipm_mv = float(parts[4])
        dead_s = float(parts[5])
        name = parts[6].strip() if len(parts) >= 7 else ""
    except Exception:
        return None

    # Sanity checks
    if event < 0 or runtime_s < 0 or dead_s < 0:
        return None
    if flag not in (0, 1):
        return None
    # v3X is 12-bit ADC
    if not (0 <= adc <= 4095):
        return None
    # SiPM mV should be non-negative; cap to reject obvious corruption
    if not (0.0 <= sipm_mv <= 6000.0):
        return None

    return event, runtime_s, flag, adc, sipm_mv, dead_s, name


def open_serial(port: str, baud: int):
    """
    Non-blocking serial. exclusive=True prevents another process from opening same port.
    """
    return serial.Serial(
        port,
        baud,
        timeout=0,          # non-blocking
        write_timeout=1,
        exclusive=True,
    )


def serial_reader_loop(ser, run_log, on_line):
    """
    Reads bytes, assembles full lines, calls on_line(str_line, ts_utc).
    Handles Linux CDC empty-read quirk without treating as disconnect.
    """
    buf = b""
    last_rx = time.time()

    while not STOP:
        try:
            n = ser.in_waiting
            chunk = ser.read(n if n else 1)
            if chunk:
                last_rx = time.time()
                buf += chunk

                # Process complete lines
                while b"\n" in buf:
                    raw_line, buf = buf.split(b"\n", 1)
                    raw_line = raw_line.rstrip(b"\r")
                    if not raw_line:
                        continue
                    s = raw_line.decode("utf-8", errors="replace").strip()
                    ts = iso_utc_now()
                    on_line(s, ts)

            else:
                # No bytes available
                time.sleep(0.01)

        except serial.SerialException as e:
            # Real port error: log + rethrow so main can reopen
            run_log.write(f"{iso_utc_now()} SERIAL_EXCEPTION {repr(e)}\n")
            fsync_file(run_log)
            raise
        except Exception as e:
            # Non-fatal: keep going
            run_log.write(f"{iso_utc_now()} SERIAL_READ_ERROR {repr(e)}\n")
            fsync_file(run_log)
            time.sleep(0.05)

        # Optional: if nothing received for a long time, just idle (not an error)
        if (time.time() - last_rx) > 60:
            last_rx = time.time()


# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="Use /dev/serial/by-id/... (recommended) or /dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--outdir", default=os.path.expanduser("~/cw_data"))
    ap.add_argument("--sensor-hz", type=float, default=1.0)
    ap.add_argument("--env-window-s", type=int, default=60)
    ap.add_argument("--sys-hz", type=float, default=0.1)
    ap.add_argument("--sea-level-hpa", type=float, default=1013.25)

    ap.add_argument("--wait-time-sync-s", type=int, default=90)
    ap.add_argument("--allow-unsynced", action="store_true", default=False)

    ap.add_argument("--wait-device-s", type=int, default=60)

    ap.add_argument("--photo", action="store_true", default=False)
    ap.add_argument("--photo-interval-s", type=int, default=3600)
    ap.add_argument("--photo-immediate", action="store_true", default=False)

    ap.add_argument("--no-bmp", action="store_true", default=False)
    ap.add_argument("--no-bno", action="store_true", default=False)

    ap.add_argument("--print-every", type=int, default=0, help="0 disables; otherwise prints every N events")

    args = ap.parse_args()

    run_n, run_folder, run_name = next_run_folder(os.path.expanduser(args.outdir))

    # Files
    cw_master_path = os.path.join(run_folder, "cosmicwatch_master.csv")
    cw_coin_path = os.path.join(run_folder, "cosmicwatch_coincidence.csv")
    cw_noncoin_path = os.path.join(run_folder, "cosmicwatch_noncoincidence.csv")
    cw_misc_path = os.path.join(run_folder, "cosmicwatch_misc.log")

    env_path = os.path.join(run_folder, "env_60s.csv")
    sys_path = os.path.join(run_folder, "system_metrics.csv")
    cam_log_path = os.path.join(run_folder, "camera.log")
    run_log_path = os.path.join(run_folder, "run.log")
    meta_path = os.path.join(run_folder, "run_metadata.json")

    run_log = open_linebuffered(run_log_path)
    cw_misc_f = open_linebuffered(cw_misc_path)
    env_f = open_linebuffered(env_path)
    sys_f = open_linebuffered(sys_path)
    cam_log_f = open_linebuffered(cam_log_path)

    # Lock (prevents double-run)
    lock_path = os.path.join(os.path.expanduser(args.outdir), ".cw_logger.lock")
    lock_f = acquire_lock(lock_path, log_f=run_log)

    run_log.write(f"{iso_utc_now()} run={run_name} boot_id={read_boot_id()} starting\n")
    run_log.write(f"{iso_utc_now()} port={args.port} baud={args.baud}\n")

    # NTP sync
    synced = wait_for_ntp_sync(args.wait_time_sync_s)
    run_log.write(f"{iso_utc_now()} ntp_synced={synced}\n")
    if not synced and not args.allow_unsynced:
        run_log.write(f"{iso_utc_now()} ERROR time_not_synced_exiting\n")
        fsync_file(run_log)
        print("[ERROR] NTP not synced. Use --allow-unsynced if you absolutely must run anyway.")
        sys.exit(2)

    # Wait for device node
    if not wait_for_path(args.port, args.wait_device_s):
        run_log.write(f"{iso_utc_now()} ERROR serial_port_not_found={args.port}\n")
        fsync_file(run_log)
        print(f"[ERROR] Serial port not found: {args.port}")
        sys.exit(3)

    # I2C init
    i2c = None
    if not args.no_bmp or not args.no_bno:
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
        except Exception as e:
            run_log.write(f"{iso_utc_now()} WARN i2c_init_failed {repr(e)}\n")
            i2c = None

    bmp = None
    if (not args.no_bmp) and i2c is not None:
        # probe 0x76 then 0x77
        for addr in (0x76, 0x77):
            try:
                bmp = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=addr)
                run_log.write(f"{iso_utc_now()} INFO bmp280_found_at_0x{addr:02x}\n")
                break
            except Exception as e:
                run_log.write(f"{iso_utc_now()} WARN bmp280_probe_fail_0x{addr:02x} {repr(e)}\n")
        if bmp is None:
            run_log.write(f"{iso_utc_now()} WARN bmp280_not_found\n")

    bno = None
    include_bno = (not args.no_bno) and (i2c is not None)
    if include_bno:
        # common BNO addresses are 0x28 and 0x29
        for addr in (0x28, 0x29):
            try:
                bno = adafruit_bno055.BNO055_I2C(i2c, address=addr)
                run_log.write(f"{iso_utc_now()} INFO bno055_found_at_0x{addr:02x}\n")
                break
            except Exception as e:
                run_log.write(f"{iso_utc_now()} WARN bno055_probe_fail_0x{addr:02x} {repr(e)}\n")
        if bno is None:
            include_bno = False
            run_log.write(f"{iso_utc_now()} WARN bno055_not_found\n")

    # Metadata
    meta = {
        "run_number": run_n,
        "run_name": run_name,
        "run_folder": run_folder,
        "start_ts_utc": iso_utc_now(),
        "boot_id": read_boot_id(),
        "serial_port_arg": args.port,
        "serial_port_realpath": os.path.realpath(args.port),
        "baud": args.baud,
        "sensor_hz": args.sensor_hz,
        "env_window_s": args.env_window_s,
        "sys_hz": args.sys_hz,
        "sea_level_hpa": args.sea_level_hpa,
        "photo_enabled": bool(args.photo),
        "photo_interval_s": args.photo_interval_s,
        "photo_immediate": bool(args.photo_immediate),
        "camera_cmd_found": camera_command(),
        "bmp_enabled": bool(bmp is not None),
        "bno_enabled": bool(include_bno),
        "python": sys.version,
    }
    safe_write_text(meta_path, json.dumps(meta, indent=2) + "\n")

    # Start threads
    th_env = threading.Thread(
        target=env_aggregate_loop,
        args=(env_f, bmp, bno, args.sensor_hz, args.env_window_s, args.sea_level_hpa, include_bno, run_log),
        daemon=True,
    )
    th_env.start()

    th_sys = threading.Thread(target=sys_loop, args=(sys_f, args.sys_hz), daemon=True)
    th_sys.start()

    if args.photo:
        th_photo = threading.Thread(
            target=photo_loop,
            args=(run_folder, args.photo_interval_s, args.photo_immediate, cam_log_f),
            daemon=True,
        )
        th_photo.start()

    # CSV writers
    def open_cw_csv(path):
        f = open_linebuffered(path)
        w = csv.writer(f)
        if os.stat(path).st_size == 0:
            w.writerow(
                [
                    "ts_utc",
                    "event",
                    "runtime_s",
                    "coincidence_flag",
                    "adc_12b",
                    "sipm_mV",
                    "deadtime_s",
                    "detector_name",
                    "raw",
                ]
            )
        return f, w

    cw_master_f, cw_master_w = open_cw_csv(cw_master_path)
    cw_coin_f, cw_coin_w = open_cw_csv(cw_coin_path)
    cw_noncoin_f, cw_noncoin_w = open_cw_csv(cw_noncoin_path)

    # Serial open
    ser = None
    while not STOP:
        try:
            ser = open_serial(args.port, args.baud)
            try:
                ser.reset_input_buffer()
            except Exception:
                pass
            break
        except Exception as e:
            run_log.write(f"{iso_utc_now()} WARN serial_open_fail {repr(e)}\n")
            fsync_file(run_log)
            time.sleep(1)

    if ser is None:
        run_log.write(f"{iso_utc_now()} ERROR serial_open_failed_final\n")
        fsync_file(run_log)
        sys.exit(4)

    run_log.write(f"{iso_utc_now()} READY logging\n")
    fsync_file(run_log)
    print(f"[INFO] Logger running. Run folder: {run_folder}")
    print("[INFO] Ctrl+C to stop cleanly.")

    lines = 0
    last_flush = time.time()

    def on_line(s: str, ts: str):
        nonlocal lines, last_flush

        parsed = parse_cw_line(s)
        if parsed is None:
            # keep raw line for audit/debug
            cw_misc_f.write(f"{ts}\t{s}\n")
            return

        event, runtime_s, flag, adc, sipm_mv, dead_s, name = parsed
        row = [ts, event, runtime_s, flag, adc, sipm_mv, dead_s, name, s]

        cw_master_w.writerow(row)
        if flag == 1:
            cw_coin_w.writerow(row)
        else:
            cw_noncoin_w.writerow(row)

        lines += 1
        if args.print_every and (lines % args.print_every == 0):
            kind = "COIN" if flag == 1 else "SING"
            print(f"[{ts[11:23]}] n={lines} last_event={event} {kind} adc={adc} sipm={sipm_mv:.3f}mV")

        # periodic flush
        if (time.time() - last_flush) > 10:
            for f in (cw_master_f, cw_coin_f, cw_noncoin_f, cw_misc_f, run_log, env_f, sys_f, cam_log_f):
                fsync_file(f)
            last_flush = time.time()

    # Main serial loop with reopen on real errors
    while not STOP:
        try:
            serial_reader_loop(ser, run_log, on_line)
        except serial.SerialException:
            # real error: try reopen
            try:
                ser.close()
            except Exception:
                pass
            time.sleep(1)
            wait_for_path(args.port, args.wait_device_s)
            try:
                ser = open_serial(args.port, args.baud)
                try:
                    ser.reset_input_buffer()
                except Exception:
                    pass
                run_log.write(f"{iso_utc_now()} INFO serial_reopened\n")
                fsync_file(run_log)
            except Exception as e:
                run_log.write(f"{iso_utc_now()} WARN serial_reopen_fail {repr(e)}\n")
                fsync_file(run_log)
                time.sleep(2)

    # Shutdown
    run_log.write(f"{iso_utc_now()} stopping\n")
    for f in (cw_master_f, cw_coin_f, cw_noncoin_f, cw_misc_f, run_log, env_f, sys_f, cam_log_f):
        fsync_file(f)
        try:
            f.close()
        except Exception:
            pass
    try:
        ser.close()
    except Exception:
        pass
    try:
        lock_f.close()
    except Exception:
        pass
    print("[INFO] Shutdown complete.")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)
    main()


