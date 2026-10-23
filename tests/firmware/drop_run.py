"""Close the port for a while and judge whether the watch kept working.

The watch lies still on a table on USB power with firmware/ flashed. The
script resets the watch and reads until 60 seconds after the first FACE line
with state 1. It then closes the port, waits, and opens the port again with
DTR and RTS low, so the watch does not reset, and reads for 150 seconds. It
saves every line with the laptop's time in seconds as gzip text, and the
"> CLOSE" and "> OPEN" lines mark the closed time. It judges the log by the pass
checks of check 10 of specs/features/09-usb-recording/validation.md. It runs
with the ESP-IDF Python, which has pyserial, and it takes about 5 minutes.

    ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/drop_run.py

With --unplug the script asks the user to unplug the USB cable instead, which
needs a battery in the watch. Check 11 uses it. With --log-only it judges a
saved log and opens no port. It exits with code 0 only when every pass check
holds.
"""
from __future__ import annotations

import argparse
import gzip
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import record_run  # noqa: E402
from record_run import Burst, bursts_of, gaps_of, kind_of, read_log  # noqa: E402
from table_run import Check, fields_of  # noqa: E402

LOG = logging.getLogger("drop_run")

REPO = HERE.parents[1]
DEFAULT_PORT = "/dev/cu.usbmodem101"
DEFAULT_LOG = REPO / "tests" / "firmware" / "drop_log.txt.gz"
DEFAULT_REPORT = REPO / "tests" / "firmware" / "drop_report.md"

CLOSE = "> CLOSE"
OPEN = "> OPEN"
BOOT_WAIT_S = 120.0
OPEN_BEFORE_S = 60.0
READ_AFTER_S = 150.0
READ_FIRST_S = 5.0
UNPLUG_WAIT_S = 300.0
# The limits of check 10.
T_LINES_MIN = 50
SETTLE_US = 15_000_000
STEP_LOW_US = 900_000
STEP_HIGH_US = 1_100_000
SPAN_MIN = 50


def wait_for_device(port: str, present: bool, seconds: float) -> bool:
    """Wait until the port's device file exists or goes, and tell whether it did."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if Path(port).exists() == present:
            return True
        time.sleep(0.2)
    return False


def read_for(ser: Any, port: str, out: Any, started: float, seconds: float, stop: str | None = None) -> Any:
    """Read and save lines for some seconds, or until a line starts with stop."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        ser, text = record_run.read_line(ser, port)
        if text is None:
            continue
        record_run.write_entry(out, started, text)
        if stop is not None and text.startswith(stop) and fields_of(text).get("state") == "1":
            break
    return ser


def read_first_line(ser: Any, port: str, out: Any, started: float) -> Any:
    """Read the first line after the port opens. When the port closed, the
    laptop dropped the bytes it held, which can end in the middle of a line, so
    the first line can be the rest of that line. Such a rest goes into the log
    as the script's own line "> PARTIAL <text>", and a whole line goes in as it
    is."""
    end = time.monotonic() + READ_FIRST_S
    while time.monotonic() < end:
        ser, text = record_run.read_line(ser, port)
        if text is None:
            continue
        if not record_run.follows_format(text):
            text = f"> PARTIAL {text}"
        record_run.write_entry(out, started, text)
        break
    return ser


def run(port: str, log_path: Path, closed_seconds: float, unplug: bool) -> None:
    """Reset the watch, close the port for a while, and read again with no reset."""
    with gzip.open(log_path, "wt") as out:
        started = time.monotonic()
        ser = record_run.open_port(port, reset=True)
        ser = read_for(ser, port, out, started, BOOT_WAIT_S, stop="FACE ")
        ser = read_for(ser, port, out, started, OPEN_BEFORE_S)
        record_run.write_entry(out, started, CLOSE)
        ser.close()
        if unplug:
            record_run.write_entry(out, started, "> UNPLUG the USB cable, wait about 60 seconds, and plug it back")
            LOG.info("Unplug the USB cable, wait about 60 seconds, and plug it back.")
            gone = wait_for_device(port, False, UNPLUG_WAIT_S)
            record_run.write_entry(out, started, f"> GONE {int(gone)}")
            back = wait_for_device(port, True, UNPLUG_WAIT_S)
            record_run.write_entry(out, started, f"> BACK {int(back)}")
        else:
            time.sleep(closed_seconds)
        record_run.write_entry(out, started, OPEN)
        ser = record_run.open_port(port, reset=False)
        ser = read_first_line(ser, port, out, started)
        ser = read_for(ser, port, out, started, READ_AFTER_S)
        ser.close()


@dataclass
class DropLog:
    """The lines of a drop log from the first B line on, with the places of CLOSE and OPEN."""

    texts: list[str]
    close: int
    open: int


def drop_log(all_texts: list[str]) -> DropLog:
    """Keep the lines from the first B line on and find CLOSE and OPEN."""
    start = record_run.first_boot_index(all_texts) or 0
    texts = all_texts[start:]
    close = texts.index(CLOSE) if CLOSE in texts else len(texts)
    opened = texts.index(OPEN) if OPEN in texts else len(texts)
    return DropLog(texts, close, opened)


def last(log: DropLog, word: str) -> dict[str, str]:
    """Give the fields of the last line with some first word."""
    found = [t for t in log.texts if t.split(" ", 1)[0] == word]
    return fields_of(found[-1]) if found else {}


def check_one_boot(log: DropLog) -> Check:
    """Item 1 checks one START line and the same B line throughout."""
    starts = sum(1 for t in log.texts if t.startswith("START "))
    boots = {t for t in log.texts if kind_of(t) == "B"}
    ok = starts == 1 and len(boots) == 1
    return Check("one boot", ok, f"{starts} START lines, {len(boots)} different B lines")


def check_t_counts(log: DropLog) -> Check:
    """Item 3 checks the T lines before CLOSE and after OPEN."""
    before = sum(1 for t in log.texts[: log.close] if kind_of(t) == "T")
    after = sum(1 for t in log.texts[log.open :] if kind_of(t) == "T")
    ok = before >= T_LINES_MIN and after >= T_LINES_MIN
    return Check("T lines on both sides", ok, f"{before} before CLOSE, {after} after OPEN")


def check_no_wait(log: DropLog) -> Check:
    """Item 4 checks that no task dropped a message while the port was closed."""
    got = {
        "line_drops": last(log, "USB_MINUTE").get("line_drops"),
        "msg_drops": last(log, "SENSOR_MINUTE").get("msg_drops"),
        "record_drops": last(log, "SENSOR_MINUTE").get("record_drops"),
        "answer_drops": last(log, "PIPELINE_MINUTE").get("answer_drops"),
        "faults": last(log, "PIPELINE_MINUTE").get("faults"),
        "screen_drops": last(log, "STATE_MINUTE").get("screen_drops"),
    }
    ok = all(v == "0" for v in got.values())
    return Check("no task waited", ok, " ".join(f"{k}={v}" for k, v in got.items()))


def check_answers(log: DropLog) -> Check:
    """Item 5 checks the answer spacing, also across the closed time."""
    t0s = {r["number"]: int(r["t0_us"]) for r in (fields_of(t) for t in log.texts if t.startswith("STRETCH "))}
    answers = [fields_of(t) for t in log.texts if t.startswith("ANSWER ") and "window=none" not in t]
    problems: list[str] = []
    widest = 0
    for a, b in zip(answers, answers[1:]):
        t0 = t0s.get(a.get("stretch", ""))
        if a.get("stretch") != b.get("stretch") or t0 is None:
            continue
        if int(a["at_us"]) < t0 + SETTLE_US or int(b["at_us"]) < t0 + SETTLE_US:
            continue
        steps = int(b["window"]) - int(a["window"])
        gap = int(b["at_us"]) - int(a["at_us"])
        if steps <= 0 or not STEP_LOW_US * steps <= gap <= STEP_HIGH_US * steps:
            problems.append(f"windows {a['window']} to {b['window']} lie {gap} us apart")
        widest = max(widest, steps)
    if widest < SPAN_MIN:
        problems.append(f"the widest pair spans {widest} windows")
    detail = f"widest pair {widest} windows, {len(problems)} problems"
    return Check("answers went on", not problems, detail + (f", first: {problems[0]}" if problems else ""))


@dataclass
class GapInfo:
    """What the T lines and the last USB_MINUTE line show about the closed time."""

    port_drops: int
    restarts: int
    gaps: list[tuple[Burst, Burst]]


def gap_info(log: DropLog) -> GapInfo:
    """Find the gaps in the T numbers and the drop counts."""
    usb = last(log, "USB_MINUTE")
    return GapInfo(int(usb.get("port_drops", "0")), int(usb.get("restarts", "0")), gaps_of(bursts_of(log.texts)))


def check_gap(log: DropLog, unplug: bool) -> Check:
    """Item 6 checks the gap in the T numbers and the B and S lines at it."""
    info = gap_info(log)
    problems: list[str] = []
    if len(info.gaps) > 1:
        problems.append(f"{len(info.gaps)} gaps in the T numbers")
    if unplug and info.port_drops == 0:
        problems.append("the unplug dropped no line")
    if info.gaps:
        a, b = info.gaps[0]
        if b.index <= log.open:
            problems.append(f"the gap after reading {a.first} lies before OPEN")
        if info.port_drops > 0:
            between = log.texts[a.index + 1 : b.index]
            latest = [t for t in log.texts[: a.index] if kind_of(t) == "S"]
            if not any(kind_of(t) == "B" for t in between) or not latest or latest[-1] not in between:
                problems.append("no B line and S line between the two T lines at the gap")
            if info.restarts < 1:
                problems.append(f"restarts={info.restarts}")
    elif info.port_drops > 0:
        problems.append(f"port_drops={info.port_drops} with no gap")
    detail = f"port_drops={info.port_drops} restarts={info.restarts} gaps={len(info.gaps)}"
    return Check("gap and repeated lines", not problems, detail + (f", first: {problems[0]}" if problems else ""))


def judge(log: DropLog, unplug: bool) -> list[Check]:
    """Give the result of every pass check of check 10."""
    return [
        check_one_boot(log),
        record_run.check_format(log.texts, "every line is whole"),
        check_t_counts(log),
        check_no_wait(log),
        check_answers(log),
        check_gap(log, unplug),
    ]


def measurements(log: DropLog) -> list[str]:
    """Give the measurements of check 10 as report lines."""
    info = gap_info(log)
    out = [f"- The last USB_MINUTE line gives port_drops={info.port_drops} and restarts={info.restarts}."]
    if info.port_drops > 0:
        out.append(f"- The watch dropped {info.port_drops} lines while nobody read the port.")
    else:
        out.append("- The watch dropped no line. This check showed only that the watch never waited on the port.")
    if info.gaps:
        a, b = info.gaps[0]
        out.append(f"- The gap in the T numbers spans {b.first - a.first - a.count} readings.")
        after_open = log.texts[log.open + 1 :]
        boot_at = next((i for i, t in enumerate(after_open) if kind_of(t) == "B"), None)
        if boot_at is not None:
            out.append(f"- {boot_at} lines from before the close arrived after the OPEN line.")
        if info.port_drops == 0:
            out.append("- The lines were lost on the laptop's side, because the T numbers have a gap.")
    else:
        out.append("- The T numbers have no gap, so the laptop's side lost no line.")
    return out


def write_report(path: Path, checks: list[Check], measured: list[str]) -> None:
    """Write the report with the checks and the measurements."""
    lines = ["# Drop run", "", "## Pass checks", ""]
    lines += [f"- {'PASS' if c.passed else 'FAIL'}: {c.name}. {c.detail}" for c in checks]
    lines += ["", "## Measurements", ""] + measured
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run or judge the drop run and give the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log-only", action="store_true")
    parser.add_argument("--closed-seconds", type=float, default=60.0)
    parser.add_argument("--unplug", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.log_only:
        run(args.port, args.log, args.closed_seconds, args.unplug)
    log = drop_log([e.text for e in read_log(args.log)])
    checks = judge(log, args.unplug)
    write_report(args.report, checks, measurements(log))
    for check in checks:
        LOG.info("%s: %s. %s", "PASS" if check.passed else "FAIL", check.name, check.detail)
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
