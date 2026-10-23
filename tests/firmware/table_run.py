"""Run the table run of feature 7 and judge it.

The watch lies still on a table on USB power. The script resets the watch
through the port, saves every line with the laptop's time in seconds, and
judges the log by the pass checks in check 9 of
specs/features/07-firmware-base/validation.md. It runs with the ESP-IDF
Python, which has pyserial.

    caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/table_run.py

With --log-only it judges a saved log and opens no port. It exits with code 0
only when every pass check holds.
"""
from __future__ import annotations

import argparse
import logging
import re
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOG = logging.getLogger("table_run")

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PORT = "/dev/cu.usbmodem101"
DEFAULT_LOG = REPO / "tests" / "firmware" / "table_log.txt"
DEFAULT_REPORT = REPO / "tests" / "firmware" / "table_report.md"

# Feature 1 measured this rate over twenty minutes with the sensor's own counter.
FEATURE1_RATE_UHZ = 114330200
RATE_TOLERANCE_PPM = 1000
TASK_NAMES = ("sensor", "pipeline", "state", "screen", "usb")
MINUTE_KINDS = ("SENSOR_MINUTE", "PIPELINE_MINUTE", "SCREEN_MINUTE", "USB_MINUTE")
LOSS_FIELDS = ("kind1_ends", "overflow", "full", "read_error", "stall", "late", "msg_drops")
FIFO_WTM = 11
ACCEL_COUNTS_PER_G = 4096.0
PORT_WAIT_S = 10.0
EXTRA_MINUTES = 3


@dataclass
class Check:
    """One pass check and its result."""

    name: str
    passed: bool
    detail: str


@dataclass
class Stretch:
    """One stretch from the STRETCH lines, the RATE lines, and the line that ended it."""

    number: int
    t0_us: int
    rate_uhz: int = 0
    end_kind: str = "open"
    end_reason: str = ""
    span_us: int | None = None
    error_us: str = ""


@dataclass
class Parsed:
    """The lines of a log, grouped by their first word."""

    texts: list[str] = field(default_factory=list)
    records: dict[str, list[dict[str, str]]] = field(default_factory=dict)


def fields_of(text: str) -> dict[str, str]:
    """Give the key=value fields of one line."""
    return dict(re.findall(r"(\w+)=(\S+)", text))


def parse_log(path: Path) -> Parsed:
    """Read a saved log. Each line holds the laptop time, a tab, and the watch's line."""
    parsed = Parsed()
    for raw in path.read_text(errors="replace").splitlines():
        text = raw.split("\t", 1)[1] if "\t" in raw else raw
        parsed.texts.append(text)
        word = text.split(" ", 1)[0]
        parsed.records.setdefault(word, []).append(fields_of(text))
    return parsed


def minute_record(parsed: Parsed, kind: str, minute: int) -> dict[str, str] | None:
    """Give the minute line of one kind for one minute, or None."""
    for record in parsed.records.get(kind, []):
        if record.get("minute") == str(minute):
            return record
    return None


def check_start(parsed: Parsed) -> Check:
    """Item 1 checks for one START line and no reset or error after it."""
    starts = [i for i, text in enumerate(parsed.texts) if text.startswith("START ")]
    if len(starts) != 1:
        return Check("one start, no reset or error", False, f"{len(starts)} START lines")
    bad = [
        text
        for text in parsed.texts[starts[0] + 1 :]
        if text.startswith("rst:") or "Guru Meditation" in text or "abort()" in text or "SENSOR_ERROR" in text
    ]
    return Check("one start, no reset or error", not bad, f"{len(bad)} bad lines" + (f", first: {bad[0]}" if bad else ""))


def check_setup(parsed: Parsed) -> Check:
    """Item 2 checks the sensor settings that the watch read back."""
    setups = parsed.records.get("SENSOR_SETUP", [])
    if len(setups) != 1:
        return Check("sensor settings", False, f"{len(setups)} SENSOR_SETUP lines")
    s = setups[0]
    try:
        ctrl1, ctrl2, ctrl3, ctrl7, fifo_ctrl = (int(s[k], 16) for k in ("ctrl1", "ctrl2", "ctrl3", "ctrl7", "fifo_ctrl"))
        ok = (
            ctrl7 & 0x03 == 0x03
            and ctrl2 & 0x0F == 0x06
            and ctrl3 & 0x0F == 0x06
            and s["gyro_range_dps"] == "1024"
            and ctrl1 & 0x0C == 0x0C
            and fifo_ctrl & 0x0F == 0x0D
            and s["fifo_wtm"] == "11"
        )
    except (KeyError, ValueError):
        return Check("sensor settings", False, "SENSOR_SETUP misses a field")
    return Check("sensor settings", ok, " ".join(f"{k}={v}" for k, v in s.items()))


def check_power(parsed: Parsed) -> Check:
    """Item 3 checks that the power chip answered and USB power is in."""
    lines = parsed.records.get("POWER", [])
    ok = len(lines) == 1 and lines[0].get("pmu") == "ok" and lines[0].get("vbus") == "1"
    return Check("power chip", ok, str(lines))


def check_tasks(parsed: Parsed) -> Check:
    """Item 4 checks the five TASK lines, their cores, and their priorities."""
    tasks: dict[str, dict[str, str]] = {}
    for record in parsed.records.get("TASK", []):
        name = record.get("name", "")
        if name in tasks:
            return Check("five tasks", False, f"two TASK lines for {name}")
        tasks[name] = record
    if sorted(tasks) != sorted(TASK_NAMES):
        return Check("five tasks", False, f"tasks {sorted(tasks)}")
    try:
        priority = {name: int(record["priority"]) for name, record in tasks.items()}
    except (KeyError, ValueError):
        return Check("five tasks", False, "a TASK line misses its priority")
    others = [priority[name] for name in TASK_NAMES if name != "sensor"]
    ok = (
        tasks["sensor"].get("core") == "1"
        and priority["sensor"] > max(others)
        and priority["usb"] < min(priority[name] for name in TASK_NAMES if name != "usb")
    )
    return Check("five tasks", ok, " ".join(f"{n}:core{tasks[n].get('core')}/p{priority[n]}" for n in TASK_NAMES))


def check_minutes(parsed: Parsed, minutes: int) -> Check:
    """Item 5 checks for every minute line of every kind."""
    missing = [
        f"{kind} {m}" for kind in MINUTE_KINDS for m in range(1, minutes + 1) if minute_record(parsed, kind, m) is None
    ]
    return Check("every minute line", not missing, f"missing {missing[:5]}" if missing else "all present")


def check_losses(parsed: Parsed, minutes: int) -> Check:
    """Item 6 checks that no reading, message, or line was lost."""
    sensor = minute_record(parsed, "SENSOR_MINUTE", minutes)
    pipeline = minute_record(parsed, "PIPELINE_MINUTE", minutes)
    usb = minute_record(parsed, "USB_MINUTE", minutes)
    if sensor is None or pipeline is None or usb is None:
        return Check("no losses", False, "a last minute line is missing")
    kind1 = [r for r in parsed.records.get("STRETCH", []) if r.get("kind") == "1"]
    counts = {name: sensor.get(name) for name in LOSS_FIELDS}
    ok = (
        all(value == "0" for value in counts.values())
        and pipeline.get("breaks") == "0"
        and usb.get("line_drops") == "0"
        and not kind1
    )
    detail = " ".join(f"{k}={v}" for k, v in counts.items())
    detail += f" breaks={pipeline.get('breaks')} line_drops={usb.get('line_drops')} kind1_lines={len(kind1)}"
    return Check("no losses", ok, detail)


def check_reading_counts(parsed: Parsed, minutes: int) -> Check:
    """Item 7 checks that the pipeline task saw the readings that the sensor task sent."""
    sensor = minute_record(parsed, "SENSOR_MINUTE", minutes)
    pipeline = minute_record(parsed, "PIPELINE_MINUTE", minutes)
    if sensor is None or pipeline is None:
        return Check("reading counts agree", False, "a last minute line is missing")
    diff = abs(int(sensor["readings"]) - int(pipeline["readings"]))
    return Check("reading counts agree", diff <= 32, f"difference {diff}")


def check_bursts(parsed: Parsed, minutes: int) -> Check:
    """Item 8 checks the burst sizes and the delay from stamp to read."""
    sensor = minute_record(parsed, "SENSOR_MINUTE", minutes)
    if sensor is None:
        return Check("burst sizes and delay", False, "the last SENSOR_MINUTE line is missing")
    bursts = int(sensor["bursts"])
    at_wtm = int(sensor["bursts_at_wtm"])
    largest = int(sensor["largest_burst"])
    delay = int(sensor["largest_delay_us"])
    ok = bursts > 0 and at_wtm >= 0.95 * bursts and largest <= 2 * FIFO_WTM and delay < 50000
    return Check("burst sizes and delay", ok, f"bursts={bursts} at_wtm={at_wtm} largest={largest} delay_us={delay}")


def rate_limits() -> tuple[int, int]:
    """Give the lowest and highest rate that item 9 allows."""
    step = FEATURE1_RATE_UHZ * RATE_TOLERANCE_PPM // 1_000_000
    return FEATURE1_RATE_UHZ - step, FEATURE1_RATE_UHZ + step


def check_rates(parsed: Parsed) -> Check:
    """Item 9 checks every rate against feature 1's rate."""
    low, high = rate_limits()
    rates = [int(r["rate_uhz"]) for r in parsed.records.get("RATE", [])]
    ok = bool(rates) and all(low <= rate <= high for rate in rates)
    return Check("rates near feature 1's rate", ok, f"{len(rates)} rates, limits {low} to {high}, rates {rates}")


def check_numbers(parsed: Parsed) -> Check:
    """Item 10 checks the first stretch and the stretch numbers."""
    stretches = parsed.records.get("STRETCH", [])
    numbers = [int(r["number"]) for r in stretches]
    ok = bool(stretches) and stretches[0].get("kind") == "start" and numbers == list(range(len(numbers)))
    return Check("stretch numbers", ok, f"numbers {numbers}")


def check_errors(parsed: Parsed) -> Check:
    """Item 11 checks that each drift end lies beyond half a reading period."""
    bad = []
    for record in parsed.records.get("STRETCH", []):
        if record.get("kind") != "2" or record.get("error_us") in (None, "none"):
            continue
        half_period = 5e11 / int(record["prev_rate_uhz"])
        if abs(float(record["error_us"])) <= half_period:
            bad.append(record["number"])
    return Check("drift ends beyond half a period", not bad, f"bad stretches {bad}" if bad else "all beyond")


def check_still(parsed: Parsed) -> Check:
    """Item 12 checks that the watch lay still and the units are right."""
    bad = []
    lines = parsed.records.get("PIPELINE_MINUTE", [])
    for record in lines:
        means = [float(x) for x in record["gyro_mean_dps"].split(",")]
        sds = [float(x) for x in record["gyro_sd_dps"].split(",")]
        accel = [float(x) for x in record["accel_mean_counts"].split(",")]
        length = sum(a * a for a in accel) ** 0.5
        if not (
            all(-10.0 <= m <= 10.0 for m in means)
            and all(sd < 1.0 for sd in sds)
            and 0.9 * ACCEL_COUNTS_PER_G <= length <= 1.1 * ACCEL_COUNTS_PER_G
        ):
            bad.append(record.get("minute"))
    return Check("still on the table", bool(lines) and not bad, f"bad minutes {bad}" if bad else f"{len(lines)} minutes")


def check_screen(parsed: Parsed, minutes: int) -> Check:
    """Item 13 checks that the screen task changed the uptime about once a second."""
    screen = minute_record(parsed, "SCREEN_MINUTE", minutes)
    if screen is None:
        return Check("screen updates", False, "the last SCREEN_MINUTE line is missing")
    updates = int(screen["updates"])
    need = 0.9 * 60 * minutes
    return Check("screen updates", updates >= need, f"updates={updates}, need {need:g}")


def judge(parsed: Parsed, minutes: int) -> list[Check]:
    """Give the result of every pass check."""
    return [
        check_start(parsed),
        check_setup(parsed),
        check_power(parsed),
        check_tasks(parsed),
        check_minutes(parsed, minutes),
        check_losses(parsed, minutes),
        check_reading_counts(parsed, minutes),
        check_bursts(parsed, minutes),
        check_rates(parsed),
        check_numbers(parsed),
        check_errors(parsed),
        check_still(parsed),
        check_screen(parsed, minutes),
    ]


def stretches_of(parsed: Parsed) -> list[Stretch]:
    """Give every stretch with its rate and the line that ended it."""
    stretches: list[Stretch] = []
    for record in parsed.records.get("STRETCH", []):
        if stretches:
            last = stretches[-1]
            last.end_kind = record.get("kind", "")
            last.end_reason = record.get("reason", "")
            last.span_us = int(record["prev_span_us"])
            last.error_us = record.get("error_us", "")
        stretches.append(Stretch(number=int(record["number"]), t0_us=int(record["t0_us"])))
    by_number = {s.number: s for s in stretches}
    for record in parsed.records.get("RATE", []):
        stretch = by_number.get(int(record["number"]))
        if stretch is not None:
            stretch.rate_uhz = int(record["rate_uhz"])
    return stretches


def write_report(path: Path, checks: list[Check], stretches: list[Stretch], minutes: int) -> None:
    """Write the report with the checks and the stretch measurements."""
    lines = [f"# Table run of {minutes} minutes", "", "## Pass checks", ""]
    lines += [f"- {'PASS' if c.passed else 'FAIL'}: {c.name}. {c.detail}" for c in checks]
    lines += ["", "## Stretches", ""]
    lines += ["| Stretch | Start (s) | Length (s) | Rate (uHz) | Ended by | Stamp error (us) |", "|---|---|---|---|---|---|"]
    start = stretches[0].t0_us if stretches else 0
    for s in stretches:
        length = f"{s.span_us / 1e6:.3f}" if s.span_us is not None else "open"
        ended = f"kind {s.end_kind} {s.end_reason}" if s.end_kind != "open" else "open"
        lines.append(
            f"| {s.number} | {(s.t0_us - start) / 1e6:.3f} | {length} | {s.rate_uhz or 'none'} | {ended} | {s.error_us} |"
        )
    closed = [s.span_us / 1e6 for s in stretches if s.span_us is not None]
    kind1 = sum(1 for s in stretches if s.end_kind == "1")
    kind2 = sum(1 for s in stretches if s.end_kind == "2")
    lines += ["", "## Counts", ""]
    lines.append(f"- Stretches: {len(stretches)}")
    lines.append(f"- Ends of the first kind: {kind1}")
    lines.append(f"- Ends of the second kind: {kind2}")
    if closed:
        lines.append(
            f"- Closed stretch lengths in seconds: shortest {min(closed):.3f}, "
            f"median {statistics.median(closed):.3f}, longest {max(closed):.3f}"
        )
    else:
        lines.append("- Closed stretch lengths in seconds: no closed stretch")
    rates = [s.rate_uhz for s in stretches if s.rate_uhz]
    changes = [f"{(b - a) / a * 1e6:+.1f}" for a, b in zip(rates, rates[1:])]
    lines.append(f"- Rate changes in parts per million: {', '.join(changes) if changes else 'none'}")
    path.write_text("\n".join(lines) + "\n")


def capture(port: str, minutes: int, log_path: Path) -> None:
    """Reset the watch, then save every line until the last minute lines arrive."""
    import serial

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = 115200
    ser.timeout = 0.5
    ser.dtr = False
    ser.rts = False
    ser.open()
    # A pulse on RTS resets the chip, as esptool's hard reset does.
    ser.rts = True
    time.sleep(0.1)
    ser.rts = False
    started = time.monotonic()
    deadline = started + (minutes + EXTRA_MINUTES) * 60
    needed = {(kind, str(minutes)) for kind in MINUTE_KINDS}
    seen: set[tuple[str, str]] = set()
    with log_path.open("w") as out:
        while time.monotonic() < deadline and not needed <= seen:
            try:
                raw = ser.readline()
            except (serial.SerialException, OSError):
                ser.close()
                ser = reopen(port)
                continue
            if not raw:
                continue
            text = raw.decode(errors="replace").rstrip("\r\n")
            out.write(f"{time.monotonic() - started:.3f}\t{text}\n")
            out.flush()
            word = text.split(" ", 1)[0]
            if word in MINUTE_KINDS:
                seen.add((word, fields_of(text).get("minute", "")))
    ser.close()


def reopen(port: str) -> Any:
    """Open the port again after the reset, waiting up to PORT_WAIT_S seconds."""
    import serial

    end = time.monotonic() + PORT_WAIT_S
    while True:
        try:
            return serial.Serial(port, 115200, timeout=0.5)
        except (serial.SerialException, OSError):
            if time.monotonic() > end:
                raise
            time.sleep(0.2)


def main(argv: list[str] | None = None) -> int:
    """Run or judge the table run and give the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log-only", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.log_only:
        capture(args.port, args.minutes, args.log)
    parsed = parse_log(args.log)
    checks = judge(parsed, args.minutes)
    write_report(args.report, checks, stretches_of(parsed), args.minutes)
    for check in checks:
        LOG.info("%s: %s. %s", "PASS" if check.passed else "FAIL", check.name, check.detail)
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
