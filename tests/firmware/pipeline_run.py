"""Run the pipeline and state tasks on a table and judge the log.

The watch lies still on a table on USB power with firmware/ flashed. The
script resets the watch through the port as table_run.py does, saves every
line with the laptop's time in seconds, and judges the log by the pass checks
in check 9 of specs/features/08-pipeline-state/validation.md. These are the 13
pass checks of table_run.py and the checks of this feature. It runs with the
ESP-IDF Python, which has pyserial.

    caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/pipeline_run.py

With --log-only it judges a saved log and opens no port. It exits with code 0
only when every pass check holds.
"""
from __future__ import annotations

import argparse
import logging
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import table_run  # noqa: E402
from table_run import Check, Parsed, fields_of, judge, parse_log, reopen  # noqa: E402

LOG = logging.getLogger("pipeline_run")

REPO = HERE.parents[1]
DEFAULT_PORT = "/dev/cu.usbmodem101"
DEFAULT_LOG = REPO / "tests" / "firmware" / "pipeline_log.txt"
DEFAULT_REPORT = REPO / "tests" / "firmware" / "pipeline_report.md"

MINUTE_KINDS = table_run.MINUTE_KINDS + ("STATE_MINUTE",)
MINUTE_US = 60_000_000
# The answers of a stretch are checked from this long after its t0.
SETTLE_US = 15_000_000
GAP_LOW_US = 900_000
GAP_HIGH_US = 1_100_000
# The last answer must come in this long before the last minute mark.
LAST_ANSWER_US = 1_100_000
SHARE_EVERY = 4
WARMING_UP = 3
SENSOR_FAULT = 4
STILL_CODES = ("0", "1")
SHARE_CODES = ("0", "1", "2")
WAITING = 3
# The face model maps codes 0, 1, and 2 to faces 0, 1, and 2, and codes 3 and 4 to Waiting.
FACE_OF_CODE = {0: 0, 1: 1, 2: 2, 3: WAITING, 4: WAITING}


@dataclass
class Line:
    """One line of the log with its place and its fields."""

    index: int
    word: str
    fields: dict[str, str]


def lines_of(parsed: Parsed) -> list[Line]:
    """Give every line of the log in order with its first word and its fields."""
    return [Line(i, text.split(" ", 1)[0], fields_of(text)) for i, text in enumerate(parsed.texts)]


def answers_of(lines: list[Line]) -> list[Line]:
    """Give the ANSWER lines in log order."""
    return [line for line in lines if line.word == "ANSWER"]


def stretch_t0s(parsed: Parsed) -> dict[int, int]:
    """Give each stretch's t0 from the STRETCH lines."""
    return {int(r["number"]): int(r["t0_us"]) for r in parsed.records.get("STRETCH", [])}


def check_detector(parsed: Parsed) -> Check:
    """Item 2 checks DETECTOR_INIT and that no error or end request came."""
    inits = parsed.records.get("DETECTOR_INIT", [])
    bad = [t for t in parsed.texts if t.startswith("PIPELINE_ERROR") or t.startswith("END_REQUEST")]
    ok = len(inits) == 1 and inits[0].get("ok") == "1" and not bad
    detail = f"DETECTOR_INIT lines {inits}, {len(bad)} error or end request lines"
    return Check("detector ready, no end request", ok, detail + (f", first: {bad[0]}" if bad else ""))


def check_windows(lines: list[Line]) -> Check:
    """Item 3 checks the window numbers and the codes of each stretch."""
    problems: list[str] = []
    next_window: dict[str, int] = {}
    for line in answers_of(lines):
        f = line.fields
        stretch = f.get("stretch", "")
        window = f.get("window", "none")
        code = f.get("code", "")
        if window == "none" or code == str(SENSOR_FAULT):
            problems.append(f"line {line.index} has window={window} code={code}")
            continue
        want = next_window.get(stretch, 0)
        if int(window) != want:
            problems.append(f"stretch {stretch} gives window {window} where {want} is next")
        next_window[stretch] = int(window) + 1
        if int(window) == 0 and code != str(WARMING_UP):
            problems.append(f"stretch {stretch} window 0 has code {code}")
        if int(window) > 0 and code not in STILL_CODES:
            problems.append(f"stretch {stretch} window {window} has code {code}")
    detail = f"{len(problems)} problems" + (f", first: {problems[0]}" if problems else "")
    return Check("window numbers and codes", not problems, detail)


def check_spacing(parsed: Parsed, lines: list[Line], minutes: int) -> Check:
    """Item 4 checks that settled answers come about once a second up to the last minute."""
    t0s = stretch_t0s(parsed)
    problems: list[str] = []
    by_stretch: dict[int, list[int]] = {}
    for line in answers_of(lines):
        stretch = int(line.fields.get("stretch", "-1"))
        at_us = int(line.fields.get("at_us", "0"))
        t0 = t0s.get(stretch)
        if t0 is None:
            problems.append(f"stretch {stretch} has no STRETCH line")
            continue
        if at_us >= t0 + SETTLE_US:
            by_stretch.setdefault(stretch, []).append(at_us)
    for stretch, times in by_stretch.items():
        for a, b in zip(times, times[1:]):
            if not GAP_LOW_US <= b - a <= GAP_HIGH_US:
                problems.append(f"stretch {stretch} has a gap of {b - a} us at {b}")
    end_us = minutes * MINUTE_US
    late_start = any(t0 > end_us - SETTLE_US for t0 in t0s.values())
    last = [int(line.fields.get("at_us", "0")) for line in answers_of(lines)]
    if not late_start and not any(end_us - LAST_ANSWER_US <= t <= end_us for t in last):
        problems.append(f"no answer from {end_us - LAST_ANSWER_US} to {end_us} us")
    detail = f"{len(problems)} problems" + (f", first: {problems[0]}" if problems else "")
    return Check("an answer each second", not problems, detail)


def check_gaps(parsed: Parsed, lines: list[Line]) -> Check:
    """Item 5 checks one GAP line for each later stretch, before its first answer."""
    problems: list[str] = []
    for record_line in (line for line in lines if line.word == "STRETCH"):
        number = record_line.fields.get("number", "")
        if number == "0":
            continue
        gaps = [line for line in lines if line.word == "GAP" and line.fields.get("stretch") == number]
        first_answer = next(
            (line.index for line in answers_of(lines) if line.fields.get("stretch") == number), len(lines)
        )
        if len(gaps) != 1:
            problems.append(f"stretch {number} has {len(gaps)} GAP lines")
        elif not record_line.index < gaps[0].index < first_answer:
            problems.append(f"the GAP line of stretch {number} is out of place")
    detail = f"{len(problems)} problems" + (f", first: {problems[0]}" if problems else "")
    return Check("a GAP line for each later stretch", not problems, detail)


def check_face(lines: list[Line]) -> Check:
    """Item 6 runs the face model over the GAP and ANSWER lines and checks every face."""
    face = WAITING
    before: int | None = None
    expected: list[int] = []
    seen: list[int] = []
    problems: list[str] = []
    for line in lines:
        if line.word == "GAP":
            new = WAITING
            before = None
        elif line.word == "ANSWER":
            state = FACE_OF_CODE.get(int(line.fields.get("code", "-1")), WAITING)
            new = state if before == state else face
            before = state
            if line.fields.get("face") != str(new):
                problems.append(f"line {line.index} shows face {line.fields.get('face')}, the model gives {new}")
        elif line.word == "FACE":
            seen.append(int(line.fields.get("state", "-1")))
            continue
        else:
            continue
        if new != face:
            expected.append(new)
            face = new
    # The capture can stop between the last change and its FACE line.
    if seen != expected and seen != expected[:-1]:
        problems.append(f"FACE lines give {seen[:10]}, the model gives {expected[:10]}")
    detail = f"{len(problems)} problems" + (f", first: {problems[0]}" if problems else "")
    return Check("face follows the model", not problems, detail)


def check_share(lines: list[Line]) -> Check:
    """Item 7 checks the share counts and the counted field against the answers."""
    tremor = still = moving = 0
    problems: list[str] = []
    for line in lines:
        f = line.fields
        if line.word == "ANSWER":
            window = f.get("window", "none")
            code = f.get("code", "")
            counts = window != "none" and int(window) > 0 and int(window) % SHARE_EVERY == 0 and code in SHARE_CODES
            if f.get("counted") != ("1" if counts else "0"):
                problems.append(f"line {line.index} has counted={f.get('counted')}")
            if counts:
                tremor += code == "0"
                still += code in STILL_CODES
                moving += code == "2"
        elif line.word == "STATE_MINUTE":
            want = {"share_tremor": str(tremor), "share_still": str(still), "share_moving": str(moving)}
            want["share"] = "none" if still == 0 else f"{tremor / still * 100:.6f}"
            got = {k: f.get(k) for k in want}
            if got != want:
                problems.append(f"minute {f.get('minute')} gives {got}, the answers give {want}")
    detail = f"{len(problems)} problems" + (f", first: {problems[0]}" if problems else "")
    return Check("share counts match the answers", not problems, detail)


def check_drops(parsed: Parsed, minutes: int) -> Check:
    """Item 8 checks that nothing was dropped and no fault answer came."""
    pipeline = table_run.minute_record(parsed, "PIPELINE_MINUTE", minutes) or {}
    state = table_run.minute_record(parsed, "STATE_MINUTE", minutes) or {}
    sensor = table_run.minute_record(parsed, "SENSOR_MINUTE", minutes) or {}
    got = {
        "faults": pipeline.get("faults"),
        "end_requests": pipeline.get("end_requests"),
        "answer_drops": pipeline.get("answer_drops"),
        "screen_drops": state.get("screen_drops"),
        "pipeline": sensor.get("pipeline"),
    }
    ok = all(v == "0" for v in got.values())
    return Check("no faults or drops", ok, " ".join(f"{k}={v}" for k, v in got.items()))


def check_screen_face(parsed: Parsed, lines: list[Line], minutes: int) -> Check:
    """Item 9 checks that the screen shows the face of the last FACE line."""
    screen_line = next(
        (
            line
            for line in lines
            if line.word == "SCREEN_MINUTE" and line.fields.get("minute") == str(minutes)
        ),
        None,
    )
    if screen_line is None:
        return Check("screen shows the face", False, "the last SCREEN_MINUTE line is missing")
    faces = [line for line in lines if line.word == "FACE" and line.index < screen_line.index]
    want = faces[-1].fields.get("state") if faces else str(WAITING)
    changes = int(screen_line.fields.get("face_changes", "-1"))
    ok = screen_line.fields.get("face") == want and changes in (len(faces), len(faces) - 1)
    detail = f"face={screen_line.fields.get('face')} face_changes={changes}, want face {want} and {len(faces)} changes"
    return Check("screen shows the face", ok, detail)


def judge_pipeline(parsed: Parsed, minutes: int) -> list[Check]:
    """Give the result of every pass check of this feature."""
    lines = lines_of(parsed)
    return [
        check_detector(parsed),
        check_windows(lines),
        check_spacing(parsed, lines, minutes),
        check_gaps(parsed, lines),
        check_face(lines),
        check_share(lines),
        check_drops(parsed, minutes),
        check_screen_face(parsed, lines, minutes),
    ]


def spread(values: list[int]) -> str:
    """Give the minimum, the median, and the maximum of some values."""
    if not values:
        return "none"
    return f"minimum {min(values)}, median {statistics.median(values):g}, maximum {max(values)}"


def measurements(parsed: Parsed, minutes: int) -> list[str]:
    """Give the measurements of check 9 as report lines."""
    lines = lines_of(parsed)
    answers = [line.fields for line in answers_of(lines) if line.fields.get("window") != "none"]
    run_us = [int(f["run_us"]) for f in answers]
    delay_us = [int(f["delay_us"]) for f in answers]
    t0s = stretch_t0s(parsed)
    out = [f"- The detector run time in microseconds is {spread(run_us)}."]
    if delay_us:
        out.append(
            f"- The delay from the burst's stamp to the end of the run in microseconds has a median of "
            f"{statistics.median(delay_us):g} and a maximum of {max(delay_us)}."
        )
    for f in answers:
        if f.get("window") == "0" and int(f["stretch"]) in t0s:
            wait = (int(f["at_us"]) - t0s[int(f["stretch"])]) / 1e6
            out.append(f"- Stretch {f['stretch']} gave its window 0 answer {wait:.3f} seconds after its t0.")
    names = ("tremor", "no tremor", "arm moving", "warming up", "sensor fault")
    counts = [sum(1 for line in answers_of(lines) if line.fields.get("code") == str(c)) for c in range(5)]
    out.append("- The answers by code are " + ", ".join(f"{n} {c}" for n, c in zip(names, counts)) + ".")
    out.append(f"- {counts[0]} tremor answers came on a still table, and each one is a false alarm.")
    state = table_run.minute_record(parsed, "STATE_MINUTE", minutes) or {}
    out.append(f"- The share at minute {minutes} is {state.get('share', 'missing')}.")
    faces = sum(1 for line in lines if line.word == "FACE")
    out.append(f"- The log holds {faces} FACE lines.")
    pipeline_free = [r.get("stack_free", "?") for r in parsed.records.get("PIPELINE_MINUTE", [])]
    state_free = [r.get("stack_free", "?") for r in parsed.records.get("STATE_MINUTE", [])]
    out.append(f"- The pipeline task's free stack in bytes was {', '.join(sorted(set(pipeline_free)))}.")
    out.append(f"- The state task's free stack in bytes was {', '.join(sorted(set(state_free)))}.")
    gaps = parsed.records.get("GAP", [])
    if gaps:
        out.append(f"- The gap path ran on the watch {len(gaps)} times.")
    else:
        out.append("- The gap path did not run on the watch, because no stretch ended.")
    return out


def write_report(path: Path, table: list[Check], own: list[Check], parsed: Parsed, minutes: int) -> None:
    """Write the report with both sets of checks and the measurements."""
    lines = [f"# Pipeline run of {minutes} minutes", "", "## Pass checks of table_run.py", ""]
    lines += [f"- {'PASS' if c.passed else 'FAIL'}: {c.name}. {c.detail}" for c in table]
    lines += ["", "## Pass checks of feature 8", ""]
    lines += [f"- {'PASS' if c.passed else 'FAIL'}: {c.name}. {c.detail}" for c in own]
    lines += ["", "## Measurements", ""]
    lines += measurements(parsed, minutes)
    lines += ["", "## Stretches", ""]
    lines += ["| Stretch | t0 (us) | Rate (uHz) | Ended by |", "|---|---|---|---|"]
    for s in table_run.stretches_of(parsed):
        ended = f"kind {s.end_kind} {s.end_reason}" if s.end_kind != "open" else "open"
        lines.append(f"| {s.number} | {s.t0_us} | {s.rate_uhz or 'none'} | {ended} |")
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
    deadline = started + (minutes + table_run.EXTRA_MINUTES) * 60
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


def main(argv: list[str] | None = None) -> int:
    """Run or judge the pipeline run and give the exit code."""
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
    table = judge(parsed, args.minutes)
    own = judge_pipeline(parsed, args.minutes)
    write_report(args.report, table, own, parsed, args.minutes)
    for check in table + own:
        LOG.info("%s: %s. %s", "PASS" if check.passed else "FAIL", check.name, check.detail)
    return 0 if all(check.passed for check in table + own) else 1


if __name__ == "__main__":
    raise SystemExit(main())
