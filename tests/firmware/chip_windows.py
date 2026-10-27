"""Run the saved windows on the chip and judge the results.

Runs check 8 of specs/features/08-pipeline-state/validation.md.
firmware/detector_check/ must be flashed on the watch. The script resets the
watch as table_run.py does and saves every line with the laptop's time in
seconds until CHECK_END arrives or 5 minutes pass. It checks the chip's
numbers against tests/detector/answers.csv with the rule of
tests/detector/test_detector.c. It runs with the ESP-IDF Python, which has
pyserial.

    ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/chip_windows.py

With --log-only it judges a saved log and opens no port. It exits with code 0
only when every pass check holds.
"""
from __future__ import annotations

import argparse
import csv
import logging
import statistics
import struct
import sys
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import table_run  # noqa: E402
from windows_bin import windows_bytes  # noqa: E402

LOG = logging.getLogger("chip_windows")

REPO = HERE.parents[1]
DEFAULT_PORT = "/dev/cu.usbmodem101"
DEFAULT_LOG = REPO / "tests" / "firmware" / "chip_windows_log.txt"
DEFAULT_REPORT = REPO / "tests" / "firmware" / "chip_windows_report.md"
WINDOWS_CSV = REPO / "tests" / "detector" / "windows.csv"
ANSWERS_CSV = REPO / "tests" / "detector" / "answers.csv"

# The constants of tests/detector/test_detector.c.
LIMIT = 0.0001
CUT_OFF = 0.029570239921802
PROB_NEAR = 0.0001
BELOW_NEAR = 0.005
GAP_NEAR = 0.0001

WINDOWS = 322
PASSES = 2
MFCC_COUNT = 12
CRC_TEXT = b"123456789"
CAPTURE_S = 5 * 60
BAD_TEXTS = ("Guru Meditation", "abort()")


@dataclass
class Row:
    """One window's detector numbers and answers."""

    mfcc: list[float]
    prob: float
    below: float
    peak: float
    at_rest: int
    tremor: int
    gap: float = 0.0


@dataclass
class Check:
    """One pass check and its result."""

    name: str
    passed: bool
    detail: str


def float32(value: float) -> float:
    """Give the 32-bit float nearest to a value, as a Python float."""
    return struct.unpack("<f", struct.pack("<f", value))[0]


def read_answers(path: Path) -> list[Row]:
    """Read the toolbox's answers for the saved windows."""
    rows: list[Row] = []
    with path.open(newline="") as handle:
        for record in csv.DictReader(handle):
            if int(record["window"]) != len(rows):
                raise ValueError(f"{path} has window {record['window']} in place {len(rows)}")
            rows.append(
                Row(
                    mfcc=[float(record[f"mfcc_{i}"]) for i in range(1, MFCC_COUNT + 1)],
                    prob=float(record["pred_tremor_proba"]),
                    below=float(record["below_tremor_power"]),
                    peak=float(record["freq_peak"]),
                    at_rest=int(record["pred_arm_at_rest"]),
                    tremor=int(record["pred_tremor_checked"]),
                    gap=float(record["peak_gap"]),
                )
            )
    return rows


def chip_row(record: dict[str, str]) -> Row:
    """Give the numbers of one CHECK_WINDOW line."""
    return Row(
        mfcc=[float32(float(x)) for x in record["mfcc"].split(",")],
        prob=float(record["prob"]),
        below=float(record["below"]),
        peak=float32(float(record["peak"])),
        at_rest=int(record["at_rest"]),
        tremor=int(record["tremor"]),
    )


def near_cut_off(toolbox: Row) -> bool:
    """Say whether a window is near a cut-off, as test_detector.c does."""
    return (
        abs(toolbox.prob - CUT_OFF) <= PROB_NEAR
        or abs(toolbox.below - 50.0) <= BELOW_NEAR
        or near_tie(toolbox)
    )


def near_tie(toolbox: Row) -> bool:
    """Say whether a window is near a peak tie, as test_detector.c does."""
    return toolbox.gap < GAP_NEAR


def rule(toolbox: Row, chip: Row) -> list[str]:
    """Apply the rule of test_detector.c to one window and give each failure."""
    failures: list[str] = []
    if len(chip.mfcc) != MFCC_COUNT:
        return [f"{len(chip.mfcc)} numbers, not {MFCC_COUNT}"]
    for i, (a, b) in enumerate(zip(toolbox.mfcc, chip.mfcc), start=1):
        if abs(b - a) > LIMIT:
            failures.append(f"mfcc_{i} differs by {abs(b - a):.3g}")
    if abs(chip.prob - toolbox.prob) > LIMIT:
        failures.append(f"probability differs by {abs(chip.prob - toolbox.prob):.3g}")
    if not near_cut_off(toolbox):
        if chip.tremor != toolbox.tremor:
            failures.append("tremor answer differs")
        if chip.at_rest != toolbox.at_rest:
            failures.append("arm at rest answer differs")
    if not near_tie(toolbox) and chip.peak != toolbox.peak:
        failures.append(f"peak {chip.peak} differs from {toolbox.peak}")
    return failures


def windows_of(parsed: table_run.Parsed, pass_number: int) -> dict[int, dict[str, str]]:
    """Give the CHECK_WINDOW records of one pass by window number."""
    out: dict[int, dict[str, str]] = {}
    for record in parsed.records.get("CHECK_WINDOW", []):
        if record.get("pass") == str(pass_number):
            out[int(record["window"])] = record
    return out


def check_crc(parsed: table_run.Parsed) -> Check:
    """Check the chip's CRC-32 of "123456789" against zlib's."""
    want = f"0x{zlib.crc32(CRC_TEXT):08x}"
    lines = parsed.records.get("CHECK_CRC", [])
    ok = len(lines) == 1 and lines[0].get("value", "").lower() == want
    return Check("CRC rule matches zlib", ok, f"want {want}, lines {lines}")


def check_start(parsed: table_run.Parsed, data: bytes) -> Check:
    """Check the size and the CRC-32 of the embedded windows."""
    want = f"0x{zlib.crc32(data):08x}"
    lines = parsed.records.get("CHECK_START", [])
    ok = (
        len(lines) == 1
        and lines[0].get("windows") == str(WINDOWS)
        and lines[0].get("bytes") == str(len(data))
        and lines[0].get("crc32", "").lower() == want
    )
    return Check("embedded windows", ok, f"want bytes={len(data)} crc32={want}, lines {lines}")


def check_runs(parsed: table_run.Parsed) -> Check:
    """Check that each pass ran every window once and nothing reset."""
    texts = parsed.texts
    crc_at = [i for i, text in enumerate(texts) if text.startswith("CHECK_CRC ")]
    window_at = [i for i, text in enumerate(texts) if text.startswith("CHECK_WINDOW ")]
    end_at = [i for i, text in enumerate(texts) if text.startswith("CHECK_END ")]
    problems: list[str] = []
    if len(window_at) != PASSES * WINDOWS:
        problems.append(f"{len(window_at)} CHECK_WINDOW lines")
    for pass_number in range(1, PASSES + 1):
        numbers = sorted(
            int(r["window"]) for r in parsed.records.get("CHECK_WINDOW", []) if r.get("pass") == str(pass_number)
        )
        if numbers != list(range(WINDOWS)):
            problems.append(f"pass {pass_number} has {len(numbers)} windows, not 0 to {WINDOWS - 1} once")
    ends = parsed.records.get("CHECK_END", [])
    if len(end_at) != 1 or ends[0].get("runs") != str(PASSES * WINDOWS):
        problems.append(f"CHECK_END lines {ends}")
    elif window_at and end_at[0] < window_at[-1]:
        problems.append("CHECK_END comes before the last CHECK_WINDOW line")
    start = crc_at[0] + 1 if crc_at else 0
    bad = [t for t in texts[start:] if t.startswith("rst:") or any(b in t for b in BAD_TEXTS)]
    if bad:
        problems.append(f"{len(bad)} reset or error lines, first: {bad[0]}")
    return Check("every window ran twice", not problems, "; ".join(problems) if problems else "644 runs")


@dataclass
class Measures:
    """The measurements of pass 1 against the toolbox."""

    worst_mfcc: float = 0.0
    worst_prob: float = 0.0
    worst_below: float = 0.0
    near_cut_off: int = 0
    near_tie: int = 0
    answer_diffs: int = 0
    peak_diffs: int = 0


def check_pass_1(parsed: table_run.Parsed, answers: list[Row]) -> tuple[Check, Measures]:
    """Apply the rule of test_detector.c to every window of pass 1."""
    records = windows_of(parsed, 1)
    m = Measures()
    failures: list[str] = []
    for w, toolbox in enumerate(answers):
        record = records.get(w)
        if record is None:
            failures.append(f"window {w} is missing")
            continue
        chip = chip_row(record)
        failures += [f"window {w}: {f}" for f in rule(toolbox, chip)]
        if len(chip.mfcc) == MFCC_COUNT:
            m.worst_mfcc = max([m.worst_mfcc] + [abs(b - a) for a, b in zip(toolbox.mfcc, chip.mfcc)])
        m.worst_prob = max(m.worst_prob, abs(chip.prob - toolbox.prob))
        if toolbox.below != 0.0:
            m.worst_below = max(m.worst_below, abs(chip.below - toolbox.below) / abs(toolbox.below))
        m.near_cut_off += int(near_cut_off(toolbox))
        m.near_tie += int(near_tie(toolbox))
        m.answer_diffs += int(chip.tremor != toolbox.tremor or chip.at_rest != toolbox.at_rest)
        m.peak_diffs += int(chip.peak != toolbox.peak)
    detail = f"{len(failures)} failures" + (f", first: {failures[0]}" if failures else "")
    return Check("pass 1 matches the toolbox", not failures, detail), m


def check_pass_2(parsed: table_run.Parsed) -> Check:
    """Check that pass 2 gives the same text as pass 1 for every number and answer."""
    first = windows_of(parsed, 1)
    second = windows_of(parsed, 2)
    differ: list[int] = []
    for w in range(WINDOWS):
        a = {k: v for k, v in first.get(w, {}).items() if k not in ("pass", "run_us")}
        b = {k: v for k, v in second.get(w, {}).items() if k not in ("pass", "run_us")}
        if not a or a != b:
            differ.append(w)
    detail = f"windows that differ: {differ[:10]}" if differ else "every window has the same text"
    return Check("pass 2 equals pass 1", not differ, detail)


def run_times(parsed: table_run.Parsed, pass_number: int) -> list[int]:
    """Give the run times of one pass in microseconds."""
    return [int(r["run_us"]) for r in windows_of(parsed, pass_number).values()]


def write_report(path: Path, checks: list[Check], m: Measures, parsed: table_run.Parsed) -> None:
    """Write the report with the checks and the measurements."""
    lines = ["# Saved windows on the chip", "", "## Pass checks", ""]
    lines += [f"- {'PASS' if c.passed else 'FAIL'}: {c.name}. {c.detail}" for c in checks]
    lines += ["", "## Pass 1 against the toolbox", ""]
    lines.append(f"- The largest difference in the 12 numbers is {m.worst_mfcc:.3g}.")
    lines.append(f"- The largest difference in the probability is {m.worst_prob:.3g}.")
    lines.append(f"- The largest relative difference in the low-frequency sum is {m.worst_below:.3g}.")
    lines.append(f"- {m.near_cut_off} windows are near a cut-off, and {m.near_tie} of them are near a peak tie.")
    lines.append(f"- An answer differs on {m.answer_diffs} windows, and the peak differs on {m.peak_diffs}.")
    lines += ["", "## Detector run time on the chip", ""]
    lines += ["| Pass | Runs | Minimum (us) | Median (us) | Maximum (us) |", "|---|---|---|---|---|"]
    for pass_number in range(1, PASSES + 1):
        times = run_times(parsed, pass_number)
        if times:
            lines.append(
                f"| {pass_number} | {len(times)} | {min(times)} | {statistics.median(times):g} | {max(times)} |"
            )
        else:
            lines.append(f"| {pass_number} | 0 | none | none | none |")
    path.write_text("\n".join(lines) + "\n")


def capture(port: str, log_path: Path) -> None:
    """Reset the watch, then save every line until CHECK_END arrives or 5 minutes pass."""
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
    deadline = started + CAPTURE_S
    with log_path.open("w") as out:
        while time.monotonic() < deadline:
            try:
                raw = ser.readline()
            except (serial.SerialException, OSError):
                ser.close()
                ser = table_run.reopen(port)
                continue
            if not raw:
                continue
            text = raw.decode(errors="replace").rstrip("\r\n")
            out.write(f"{time.monotonic() - started:.3f}\t{text}\n")
            out.flush()
            if text.startswith("CHECK_END "):
                break
    ser.close()


def main(argv: list[str] | None = None) -> int:
    """Run or judge the chip check and give the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log-only", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.log_only:
        capture(args.port, args.log)
    parsed = table_run.parse_log(args.log)
    answers = read_answers(ANSWERS_CSV)
    pass_1, measures = check_pass_1(parsed, answers)
    checks = [
        check_crc(parsed),
        check_start(parsed, windows_bytes(WINDOWS_CSV)),
        check_runs(parsed),
        pass_1,
        check_pass_2(parsed),
    ]
    write_report(args.report, checks, measures, parsed)
    for check in checks:
        LOG.info("%s: %s. %s", "PASS" if check.passed else "FAIL", check.name, check.detail)
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
