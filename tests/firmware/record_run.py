"""Run the full recording on a table and judge the log.

Runs check 8 of specs/features/09-usb-recording/validation.md. The watch lies
still on a table on USB power with firmware/ flashed. The script resets the
watch as pipeline_run.py does and saves every line with the laptop's time in
seconds as gzip text. It judges the log by the 13 pass checks of table_run.py,
the 8 pass checks of pipeline_run.py on the diagnostic lines, and the checks
of the record lines. It runs with the ESP-IDF Python, which has pyserial.

    caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/record_run.py

With --log-only it judges a saved log and opens no port. It exits with code 0
only when every pass check holds.

A run with the watch judges the log by the rules of FIRMWARE_VERSION in
firmware/main/tasks.h, so the B line must give that version. With --log-only
the judge takes the version from the log's first B line instead, because the
firmware changes after a log is saved. It refuses a version that it has no
rules for. The report names the version.

The file also holds the log and record line helpers that the other run
scripts import.
"""
from __future__ import annotations

import argparse
import gzip
import logging
import re
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pipeline_run  # noqa: E402
import table_run  # noqa: E402
from table_run import Check, Parsed, fields_of  # noqa: E402

LOG = logging.getLogger("record_run")

REPO = HERE.parents[1]
FORMAT_DOC = REPO / "core" / "recording_format.md"
TABLES_HEADER = REPO / "core" / "detector_tables.h"
TASKS_HEADER = REPO / "firmware" / "main" / "tasks.h"
DEFAULT_PORT = "/dev/cu.usbmodem101"
DEFAULT_LOG = REPO / "tests" / "firmware" / "record_log.txt.gz"
DEFAULT_REPORT = REPO / "tests" / "firmware" / "record_report.md"

RANGE_DPS = 1024
COUNT_MIN = -32768
COUNT_MAX = 32767
# The capture reads this long after the last minute lines, so the R lines of
# the last bursts arrive too.
TAIL_S = 2.0
# ESP-IDF's log lines start with one of these.
IDF_LOG_STARTS = ("I (", "W (", "E (", "D (", "V (")
DIAGNOSTIC = re.compile(r"^[A-Z][A-Z0-9_]{2,}( |$)")
SCRIPT_LINE = "> "


def record_patterns(doc: Path = FORMAT_DOC) -> dict[str, re.Pattern[str]]:
    """Read the pattern of each record line from the table in core/recording_format.md."""
    patterns: dict[str, re.Pattern[str]] = {}
    for row in doc.read_text().splitlines():
        match = re.match(r"^\| ([A-Z]) \|.*\| `(\^.*\$)` \|$", row)
        if match:
            patterns[match.group(1)] = re.compile(match.group(2))
    return patterns


PATTERNS = record_patterns()


def firmware_version(header: Path = TASKS_HEADER) -> int:
    """Read FIRMWARE_VERSION from firmware/main/tasks.h."""
    match = re.search(r"^#define FIRMWARE_VERSION (\d+)", header.read_text(), re.MULTILINE)
    if match is None:
        raise ValueError(f"{header} gives no FIRMWARE_VERSION")
    return int(match.group(1))


FIRMWARE_VERSION = firmware_version()
# The firmware versions whose saved logs this judge has rules for. Version 9
# added the record lines and the commands. Version 11 added the face, the D
# line, and new diagnostic lines. The checks of this file and of
# command_run.py are the same for both versions. Version 12 added fields at
# the ends of the minute lines and the LINE_CUT line, and these checks treat
# it as version 11.
KNOWN_VERSIONS = (9, 11, 12)
READ_CHUNK = 1 << 16


class UnknownVersion(ValueError):
    """A saved log gives a firmware version that the judge has no rules for."""


@dataclass
class Entry:
    """One line of a saved log with the laptop's time in seconds."""

    seconds: float
    text: str


@dataclass
class SavedLog:
    """The lines of a saved log, and whether its gzip stream ends early."""

    entries: list[Entry]
    cut_short: bool


def read_gzip_text(path: Path) -> tuple[list[str], bool]:
    """Read the lines of a gzip text file, and tell whether the file was cut short.

    A recording that stopped without closing its file ends in the middle of
    the gzip stream. The lines read before the cut are kept, and a last line
    with no newline is dropped, because it may be part of a line.
    """
    data = bytearray()
    cut_short = False
    with gzip.open(path, "rb") as source:
        while True:
            try:
                chunk = source.read(READ_CHUNK)
            except EOFError:
                cut_short = True
                break
            if not chunk:
                break
            data += chunk
    lines = data.decode(errors="replace").splitlines()
    if cut_short and lines and not data.endswith(b"\n"):
        lines.pop()
    return lines, cut_short


def load_log(path: Path) -> SavedLog:
    """Read a gzip log. Each line holds the laptop time, a tab, and the text."""
    raw_lines, cut_short = read_gzip_text(path)
    entries: list[Entry] = []
    for raw in raw_lines:
        stamp, _, text = raw.partition("\t")
        try:
            seconds = float(stamp)
        except ValueError:
            seconds, text = 0.0, raw
        entries.append(Entry(seconds, text))
    if cut_short:
        LOG.warning("%s was cut short. The judge uses the %d whole lines before the cut.", path, len(entries))
    return SavedLog(entries, cut_short)


def read_log(path: Path) -> list[Entry]:
    """Read a gzip log and give its lines."""
    return load_log(path).entries


def write_entry(out: Any, started: float, text: str) -> None:
    """Write one line to an open gzip log with the laptop's time."""
    out.write(f"{time.monotonic() - started:.3f}\t{text}\n")


def kind_of(text: str) -> str:
    """Give the letter of a record line, or an empty text for any other line."""
    if len(text) >= 2 and text[1] == "," and text[0] in PATTERNS:
        return text[0]
    return ""


def is_record(text: str) -> bool:
    """Tell a line that matches the pattern of its record line."""
    kind = kind_of(text)
    return bool(kind) and PATTERNS[kind].match(text) is not None


def follows_format(text: str) -> bool:
    """Tell a line that is a whole record line or a diagnostic line."""
    if text.startswith(IDF_LOG_STARTS):
        return False
    return is_record(text) or DIAGNOSTIC.match(text) is not None


def record_fields(text: str) -> list[str]:
    """Give the fields of a record line after its letter."""
    return text.split(",")[1:]


def first_boot_index(texts: list[str]) -> int | None:
    """Give the place of the first B line, or None."""
    return next((i for i, text in enumerate(texts) if kind_of(text) == "B"), None)


def check_format(texts: list[str], name: str = "every line follows the format") -> Check:
    """Check that every line from the first B line on is a record line or a diagnostic line.
    The script's own lines, which start with "> ", are left out."""
    start = first_boot_index(texts)
    if start is None:
        return Check(name, False, "no B line")
    bad = [
        text for text in texts[start:] if not text.startswith(SCRIPT_LINE) and not follows_format(text)
    ]
    return Check(name, not bad, f"{len(bad)} bad lines" + (f", first: {bad[0]!r}" if bad else ""))


def table_hash(header: Path = TABLES_HEADER) -> str:
    """Read DET_MODEL_SHA256 from core/detector_tables.h."""
    match = re.search(r'^#define DET_MODEL_SHA256 "([0-9a-f]{64})"', header.read_text(), re.MULTILINE)
    if match is None:
        raise ValueError(f"{header} gives no DET_MODEL_SHA256")
    return match.group(1)


def boot_version(text: str) -> int | None:
    """Give the firmware version of a B line, or None when the line breaks the format."""
    match = PATTERNS["B"].match(text)
    return int(match.group(3)) if match is not None else None


def judged_version(texts: list[str], live: bool, known: tuple[int, ...] = KNOWN_VERSIONS) -> int:
    """Give the firmware version whose rules judge a log.

    A run with the watch is judged by FIRMWARE_VERSION, so a watch with other
    firmware fails the B line check. A saved log is judged by the version of
    its first B line, which must be one of the known versions. A saved log
    with no good B line is judged by FIRMWARE_VERSION, and its B line check
    fails. It raises UnknownVersion for a version the judge does not know.
    """
    if live:
        return FIRMWARE_VERSION
    start = first_boot_index(texts)
    version = boot_version(texts[start]) if start is not None else None
    if version is None:
        return FIRMWARE_VERSION
    if version not in known:
        names = ", ".join(str(v) for v in known)
        raise UnknownVersion(
            f"the log's B line gives firmware version {version}, and this judge knows versions {names}"
        )
    return version


def version_note(version: int, live: bool) -> str:
    """Give the report's sentence that names the firmware version of the rules."""
    source = "firmware/main/tasks.h" if live else "the log's first B line"
    return f"The judge applies the rules of firmware version {version}, which {source} gives."


def cut_notes(saved: SavedLog) -> list[str]:
    """Give the report's sentence for a log whose gzip file was cut short, or no sentence."""
    if not saved.cut_short:
        return []
    count = len(saved.entries)
    return [f"The log's gzip file was cut short, so the judge used the {count} whole lines before the cut."]


def report_notes(saved: SavedLog, version: int, live: bool) -> list[str]:
    """Give the report lines that name the version and say whether the log was cut short."""
    return [version_note(version, live), *cut_notes(saved)]


def boot_problems(text: str, version: int) -> list[str]:
    """Give the problems of one B line, or an empty list when it is good."""
    match = PATTERNS["B"].match(text)
    if match is None:
        return [f"B line {text!r} breaks the format"]
    problems = []
    if int(match.group(3)) != version:
        problems.append(f"version {match.group(3)}")
    if match.group(4) != table_hash():
        problems.append(f"hash {match.group(4)}")
    return problems


def check_boot(texts: list[str], version: int) -> Check:
    """Check one good B line before the START line. The texts start at
    the first B line."""
    boots = [i for i, text in enumerate(texts) if kind_of(text) == "B"]
    starts = [i for i, text in enumerate(texts) if text.startswith("START ")]
    if len(boots) != 1 or len(starts) != 1:
        return Check("one B line before START", False, f"{len(boots)} B lines, {len(starts)} START lines")
    problems = boot_problems(texts[boots[0]], version)
    if boots[0] > starts[0]:
        problems.append("the B line comes after START")
    detail = texts[boots[0]]
    return Check("one B line before START", not problems, detail + (f", {problems}" if problems else ""))


@dataclass
class Burst:
    """One T line and the R lines that follow it."""

    index: int
    first: int
    count: int
    stamp_us: int
    readings: list[list[int]]


def bursts_of(texts: list[str]) -> list[Burst]:
    """Give each T line with the R lines that follow it before the next T line."""
    bursts: list[Burst] = []
    for i, text in enumerate(texts):
        kind = kind_of(text)
        if kind == "T" and is_record(text):
            first, count, stamp = (int(v) for v in record_fields(text))
            bursts.append(Burst(i, first, count, stamp, []))
        elif kind == "R" and is_record(text) and bursts:
            bursts[-1].readings.append([int(v) for v in record_fields(text)])
    return bursts


def burst_problems(burst: Burst, last: bool) -> list[str]:
    """Give the problems of one burst's R lines. The last burst may miss R
    lines, because the capture can stop in the middle of it."""
    numbers = [r[0] for r in burst.readings]
    want = list(range(burst.first, burst.first + burst.count))
    problems = []
    if numbers != want and not (last and numbers == want[: len(numbers)]):
        problems.append(f"T line at reading {burst.first} has R numbers {numbers[:3]}... for count {burst.count}")
    if any(not COUNT_MIN <= v <= COUNT_MAX for r in burst.readings for v in r[1:]):
        problems.append(f"T line at reading {burst.first} has a count out of range")
    return problems


def gaps_of(bursts: list[Burst]) -> list[tuple[Burst, Burst]]:
    """Give each two T lines in a row whose reading numbers do not follow on."""
    return [(a, b) for a, b in zip(bursts, bursts[1:]) if b.first != a.first + a.count]


def check_bursts(texts: list[str], readings_needed: int) -> Check:
    """Check the T and R lines from reading 0 with no gap and no overlap."""
    bursts = bursts_of(texts)
    problems: list[str] = []
    if not bursts or bursts[0].first != 0:
        problems.append("the first T line does not start at reading 0")
    for a, b in gaps_of(bursts):
        problems.append(f"T line at reading {b.first} follows T line at reading {a.first} with count {a.count}")
    for a, b in zip(bursts, bursts[1:]):
        if b.stamp_us <= a.stamp_us:
            problems.append(f"T line at reading {b.first} has a stamp that does not rise")
    for n, burst in enumerate(bursts):
        problems += burst_problems(burst, n == len(bursts) - 1)
    covered = max((r[0] for b in bursts for r in b.readings), default=-1) + 1
    if covered < readings_needed:
        problems.append(f"the R lines cover {covered} readings, the last SENSOR_MINUTE gives {readings_needed}")
    detail = f"{len(bursts)} T lines, {covered} readings, {len(problems)} problems"
    return Check("T and R lines", not problems, detail + (f", first: {problems[0]}" if problems else ""))


def diagnostic_parsed(texts: list[str]) -> Parsed:
    """Give the lines that are not record lines, grouped as table_run.py groups them."""
    parsed = Parsed()
    for text in texts:
        if kind_of(text):
            continue
        parsed.texts.append(text)
        parsed.records.setdefault(text.split(" ", 1)[0], []).append(fields_of(text))
    return parsed


def check_stretches(texts: list[str], parsed: Parsed) -> Check:
    """Check the S lines of each stretch against its STRETCH and RATE lines."""
    s_lines: dict[int, list[tuple[int, list[str]]]] = {}
    first_t: dict[int, int] = {}
    t_stamp: dict[int, int] = {}
    for i, text in enumerate(texts):
        if kind_of(text) == "S" and is_record(text):
            fields = record_fields(text)
            s_lines.setdefault(int(fields[0]), []).append((i, fields))
        elif kind_of(text) == "T" and is_record(text):
            first, _, stamp = record_fields(text)
            first_t.setdefault(int(first), i)
            t_stamp.setdefault(int(first), int(stamp))
    rates = {int(r["number"]): r["rate_uhz"] for r in parsed.records.get("RATE", [])}
    problems: list[str] = []
    stretches = parsed.records.get("STRETCH", [])
    for record in stretches:
        number = int(record["number"])
        lines = s_lines.get(number, [])
        if not lines or len(lines) > 2 or (len(lines) == 2 and lines[0][1][3] != "0"):
            problems.append(f"stretch {number} has {len(lines)} S lines")
            continue
        for _, fields in lines:
            if fields[1] != record["first"] or fields[2] != record["t0_us"] or fields[4] != str(RANGE_DPS):
                problems.append(f"stretch {number} has the S line {','.join(fields)}")
        if lines[-1][1][3] != rates.get(number, "0"):
            problems.append(f"stretch {number} ends with rate {lines[-1][1][3]}, RATE gives {rates.get(number)}")
        first = int(record["first"])
        if first not in first_t or lines[0][0] > first_t[first] or t_stamp[first] != int(record["t0_us"]):
            problems.append(f"stretch {number} has no first T line after its S line with stamp t0")
    extra = sorted(set(s_lines) - {int(r["number"]) for r in stretches})
    if extra:
        problems.append(f"S lines for stretches {extra} with no STRETCH line")
    detail = f"{len(stretches)} stretches, {len(problems)} problems"
    return Check("S lines", not problems, detail + (f", first: {problems[0]}" if problems else ""))


def check_windows(texts: list[str]) -> Check:
    """Check one W line for each ANSWER line with the same values and text."""
    answers = [fields_of(t) for t in texts if t.startswith("ANSWER ")]
    w_lines = [record_fields(t) for t in texts if kind_of(t) == "W"]
    problems: list[str] = []
    if len(answers) != len(w_lines):
        problems.append(f"{len(answers)} ANSWER lines and {len(w_lines)} W lines")
    for n, (a, w) in enumerate(zip(answers, w_lines)):
        window = "" if a.get("window") == "none" else a.get("window")
        numbers = [("" if a.get(k) == "none" else a.get(k)) for k in ("prob", "below", "peak")]
        want = [a.get("stretch"), window, a.get("code")] + numbers
        if w != want:
            problems.append(f"W line {n} gives {','.join(w)}, its ANSWER line gives {','.join(map(str, want))}")
    detail = f"{len(w_lines)} W lines, {len(problems)} problems"
    return Check("a W line for each answer", not problems, detail + (f", first: {problems[0]}" if problems else ""))


def check_faces(texts: list[str]) -> Check:
    """Check one F line for each FACE line with the same time and state."""
    faces = [fields_of(t) for t in texts if t.startswith("FACE ")]
    f_lines = [record_fields(t) for t in texts if kind_of(t) == "F"]
    want = [[f.get("at_us"), f.get("state")] for f in faces]
    ok = f_lines == want
    detail = f"{len(faces)} FACE lines and {len(f_lines)} F lines"
    if not ok:
        detail += f", F lines {f_lines[:5]}, FACE lines {want[:5]}"
    return Check("an F line for each face change", ok, detail)


def check_no_command_lines(texts: list[str]) -> Check:
    """Check that the log holds no D line and no A line."""
    found = [t for t in texts if kind_of(t) in ("D", "A")]
    return Check("no D or A line", not found, f"{len(found)} lines" + (f", first: {found[0]}" if found else ""))


def check_drops(parsed: Parsed, minutes: int) -> Check:
    """Check that the recording dropped nothing and took no command."""
    sensor = table_run.minute_record(parsed, "SENSOR_MINUTE", minutes) or {}
    usb = table_run.minute_record(parsed, "USB_MINUTE", minutes) or {}
    got = {
        "record_drops": sensor.get("record_drops"),
        "line_drops": usb.get("line_drops"),
        "port_drops": usb.get("port_drops"),
        "restarts": usb.get("restarts"),
        "commands": usb.get("commands"),
    }
    ok = all(v == "0" for v in got.values())
    return Check("no drops and no commands", ok, " ".join(f"{k}={v}" for k, v in got.items()))


def judge_record(texts: list[str], parsed: Parsed, minutes: int, version: int) -> list[Check]:
    """Give the result of every pass check of the record lines."""
    sensor = table_run.minute_record(parsed, "SENSOR_MINUTE", minutes) or {}
    return [
        check_boot(texts, version),
        check_format(texts),
        check_stretches(texts, parsed),
        check_bursts(texts, int(sensor.get("readings", "0"))),
        check_windows(texts),
        check_faces(texts),
        check_no_command_lines(texts),
        check_drops(parsed, minutes),
    ]


def measurements(entries: list[Entry], parsed: Parsed, minutes: int) -> list[str]:
    """Give the measurements as report lines."""
    texts = [e.text for e in entries]
    start = first_boot_index(texts) or 0
    out = [f"- The log holds {start} lines before the B line."]
    usb = table_run.minute_record(parsed, "USB_MINUTE", minutes) or {}
    if "bytes" in usb:
        rate = int(usb["bytes"]) / (60 * minutes)
        out.append(f"- USB_MINUTE gives {rate:.0f} bytes a second over {minutes} minutes.")
    after = entries[start:]
    if len(after) > 1 and after[-1].seconds > after[0].seconds:
        span = after[-1].seconds - after[0].seconds
        size = sum(len(e.text) + 1 for e in after)
        out.append(f"- The log gives {size / span:.0f} bytes a second and {len(after) / span:.0f} lines a second.")
        later = [e.seconds for e in after if e.seconds >= after[0].seconds + 60]
        gaps = [b - a for a, b in zip(later, later[1:])]
        if gaps:
            out.append(
                f"- The largest gap between two line arrivals after the first minute is {max(gaps):.3f} seconds."
            )
    for kind in ("PIPELINE_MINUTE", "STATE_MINUTE", "USB_MINUTE"):
        free = [r.get("stack_free", "?") for r in parsed.records.get(kind, [])]
        out.append(f"- {kind} gives the free stack in bytes at each minute as {', '.join(free) or 'none'}.")
    return out + pipeline_run.measurements(parsed, minutes)


def write_report(
    path: Path,
    sections: list[tuple[str, list[Check]]],
    measured: list[str],
    parsed: Parsed,
    minutes: int,
    notes: list[str],
) -> None:
    """Write the report with the notes, every set of checks, and the measurements."""
    lines = [f"# Recording run of {minutes} minutes", ""] + notes + [""]
    for title, checks in sections:
        lines += [f"## {title}", ""]
        lines += [f"- {'PASS' if c.passed else 'FAIL'}: {c.name}. {c.detail}" for c in checks]
        lines.append("")
    lines += ["## Measurements", ""] + measured
    lines += ["", "## Stretches", ""]
    lines += ["| Stretch | t0 (us) | Rate (uHz) | Ended by |", "|---|---|---|---|"]
    for s in table_run.stretches_of(parsed):
        ended = f"kind {s.end_kind} {s.end_reason}" if s.end_kind != "open" else "open"
        lines.append(f"| {s.number} | {s.t0_us} | {s.rate_uhz or 'none'} | {ended} |")
    path.write_text("\n".join(lines) + "\n")


# The runs that read through this file open the port with table_run's helper.
open_port = table_run.open_port


def read_line(ser: Any, port: str) -> tuple[Any, str | None]:
    """Read one line. After a port error, open the port again with no reset."""
    import serial

    try:
        raw = ser.readline()
    except (serial.SerialException, OSError):
        ser.close()
        return table_run.reopen(port), None
    if not raw:
        return ser, None
    return ser, raw.decode(errors="replace").rstrip("\r\n")


def capture(port: str, minutes: int, log_path: Path) -> None:
    """Reset the watch, then save every line until the last minute lines arrive."""
    ser = open_port(port, reset=True)
    started = time.monotonic()
    deadline = started + (minutes + table_run.EXTRA_MINUTES) * 60
    needed = {(kind, str(minutes)) for kind in pipeline_run.MINUTE_KINDS}
    seen: set[tuple[str, str]] = set()
    with gzip.open(log_path, "wt") as out:
        while time.monotonic() < deadline:
            if needed <= seen:
                deadline = min(deadline, time.monotonic() + TAIL_S)
                needed = set()
            ser, text = read_line(ser, port)
            if text is None:
                continue
            write_entry(out, started, text)
            word = text.split(" ", 1)[0]
            if word in pipeline_run.MINUTE_KINDS:
                seen.add((word, fields_of(text).get("minute", "")))
    ser.close()


def main(argv: list[str] | None = None) -> int:
    """Run or judge the recording run and give the exit code."""
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
    saved = load_log(args.log)
    entries = saved.entries
    # Skip every line before the first B line. They come from the chip's ROM,
    # or from before the reset when the laptop still held them.
    texts = [e.text for e in entries]
    texts = texts[first_boot_index(texts) or 0 :]
    try:
        version = judged_version(texts, not args.log_only)
    except UnknownVersion as error:
        LOG.error("The judge refuses the log: %s.", error)
        return 1
    parsed = diagnostic_parsed(texts)
    sections = [
        ("Pass checks of table_run.py", table_run.judge(parsed, args.minutes)),
        ("Pass checks of pipeline_run.py", pipeline_run.judge_pipeline(parsed, args.minutes)),
        ("Pass checks of the record lines", judge_record(texts, parsed, args.minutes, version)),
    ]
    write_report(args.report, sections, measurements(entries, parsed, args.minutes), parsed, args.minutes,
                 report_notes(saved, version, not args.log_only))
    checks = [c for _, section in sections for c in section]
    for check in checks:
        LOG.info("%s: %s. %s", "PASS" if check.passed else "FAIL", check.name, check.detail)
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
