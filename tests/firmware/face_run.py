"""Run the face's scripted check on the watch and judge the log.

Runs check 9 of specs/features/11-watch-face/validation.md. The watch lies
still on a table on USB power with firmware/ flashed, and nobody touches it.
In order, the script resets the watch, sends TONE,1, CLOCK, and
SCHEDULE,FaceTest,<m> with m the next whole minute at least 90 seconds ahead,
waits for the dose to become due and to end, sends TONE,0 and a second
schedule in the same way, waits for the second dose to become due, sends
SESSION, and puts the settings of the boot back. It saves
every line with the laptop's time in seconds as gzip text, and each command
and the reset go into the log as lines that start with "> ". It runs with the
ESP-IDF Python, which has pyserial, and takes about 22 minutes.

    caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/face_run.py

The judge reads the log alone, so --log-only gives the same result. It exits
with code 0 only when every pass check holds. A run with the watch needs the B
line to give FIRMWARE_VERSION from firmware/main/tasks.h and the views to show
the looks of the firmware now. With --log-only the judge applies the rules of
the version in the log's B line, as record_run.py does.
"""
from __future__ import annotations

import argparse
import gzip
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import command_run  # noqa: E402
import record_run  # noqa: E402
from command_run import Line, Runner  # noqa: E402
from record_run import Entry, kind_of, record_fields  # noqa: E402
from table_run import Check, fields_of  # noqa: E402

LOG = logging.getLogger("face_run")

REPO = HERE.parents[1]
DEFAULT_PORT = "/dev/cu.usbmodem101"
DEFAULT_LOG = REPO / "tests" / "firmware" / "face_log.txt.gz"
DEFAULT_REPORT = REPO / "tests" / "firmware" / "face_report.md"

DOSE_NAME = "FaceTest"
# A dose minute lies at least this long after the schedule command.
LEAD_S = 90
# The script waits this long after each dose time and after the first dose's
# end, and this long after the SESSION command.
DUE_WAIT_S = 10
SESSION_WAIT_S = 5.0
BOOT_WAIT_S = 120.0
DUE_US = 900_000_000
DAY_US = 86_400_000_000
MINUTE_US = 60_000_000

# Pass limits.
START_WITHIN_S = 30.0
INTERNAL_MIN = 10240
VIEW_WITHIN_US = 1_100_000
DUE_LATE_US = 1_100_000
SCHEDULE_VIEW_S = 2.0
TONE_PLAY_S = 1.0
SESSION_VIEW_S = 2.0
UPDATES_MIN = 54
STACK_MIN = 512
# The share counts the windows whose number divides by 4, leaves out window 0,
# and puts each in a block of 10 minutes. A block is hollow with under 30
# counted still windows, which is 2 minutes of still time.
SHARE_EVERY = 4
BLOCK_US = 600_000_000
BLOCKS_KEPT = 12
HOLLOW_BELOW = 30

# The circle and its colour for each face state in the firmware now.
LOOKS = {
    0: ("fill", "1b2e42"),
    1: ("outline", "26292b"),
    2: ("fill", "2a7242"),
    3: ("outline", "5c6265"),
    4: ("fill", "3f2559"),
}
# The looks that version 11 had from feature 11 on 23 October 2026 until
# commit 7f6b90e on 25 October 2026. Rest, which is state 1, had the filled
# green circle, and Arm moving had the dark outline. face_log.txt.gz was
# recorded with them.
FIRST_LOOKS = {**LOOKS, 1: ("fill", "2a7242"), 2: ("outline", "26292b")}
Looks = dict[int, tuple[str, str]]
# The looks of each firmware version, with a name for the report. Commit
# 7f6b90e swapped the looks of states 1 and 2 and kept version 11, so a saved
# log of version 11 may show either set. Version 9 had no face, and version
# 12 has only the looks since 7f6b90e.
LOOKS_BY_VERSION: dict[int, list[tuple[str, Looks]]] = {
    11: [
        ("the looks since commit 7f6b90e", LOOKS),
        ("the looks before commit 7f6b90e", FIRST_LOOKS),
    ],
    12: [("the looks since commit 7f6b90e", LOOKS)],
}
KNOWN_VERSIONS = tuple(LOOKS_BY_VERSION)


def dose_minute(now: datetime) -> int:
    """Give the minute of the local day that is the next whole minute at least LEAD_S seconds after now."""
    target = now + timedelta(seconds=LEAD_S)
    whole = target.replace(second=0, microsecond=0)
    if whole != target:
        whole += timedelta(minutes=1)
    return whole.hour * 60 + whole.minute


def dose_epoch(now: datetime, minute: int) -> float:
    """Give the laptop time in seconds since 1970 of the next local time with this minute of the day."""
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    at = day + timedelta(minutes=minute)
    if at < now:
        at += timedelta(days=1)
    return at.timestamp()


def send_schedule(r: Runner) -> float:
    """Send a schedule for the next dose minute and give the dose's laptop time."""
    now = datetime.now().astimezone()
    minute = dose_minute(now)
    command_run.send(r, f"SCHEDULE,{DOSE_NAME},{minute}")
    return dose_epoch(now, minute)


def run(port: str, log_path: Path) -> None:
    """Run every step on the watch."""
    with gzip.open(log_path, "wt") as out:
        r = command_run.make_runner(port, out)
        command_run.reset_watch(r)
        command_run.read_until(r, command_run.is_face(1), BOOT_WAIT_S)
        boot_settings = r.boot_settings or {}
        command_run.send(r, "TONE,1")
        offset = datetime.now().astimezone().utcoffset() or timedelta(0)
        command_run.send(r, f"CLOCK,{time.time_ns() // 1000},{int(offset.total_seconds()) // 60}")
        first = send_schedule(r)
        command_run.read_until_epoch(r, first + DUE_WAIT_S)
        command_run.read_until_epoch(r, first + DUE_US / 1e6 + DUE_WAIT_S)
        command_run.send(r, "TONE,0")
        second = send_schedule(r)
        command_run.read_until_epoch(r, second + DUE_WAIT_S)
        command_run.send(r, "SESSION")
        end = time.monotonic() + SESSION_WAIT_S
        while time.monotonic() < end:
            command_run.read(r)
        for text in command_run.restore_commands(boot_settings):
            command_run.send(r, text)
        r.ser.close()


# ---------------------------------------------------------------- the log


@dataclass
class FaceLog:
    """The parts of a face log that the checks use. The lines start at the first B line."""

    lines: list[Line]
    sent: list[command_run.Sent]
    offset_us: int | None
    clock_answer: Line | None


def parse(entries: list[Entry]) -> FaceLog:
    """Read the log from its first B line on and find each command's answer."""
    texts = [e.text for e in entries]
    start = record_run.first_boot_index(texts) or 0
    lines = [
        Line(i - start, e.seconds, e.text, e.text.split(" ", 1)[0], fields_of(e.text))
        for i, e in enumerate(entries)
        if i >= start
    ]
    sent = [command_run.sent_from(lines, line) for line in lines if line.text.startswith("> ")
            and line.text != f"> {command_run.RESET}"]
    clock = next((s for s in sent if s.text.startswith("CLOCK,")), None)
    offset = None
    if clock is not None:
        found = [line for line in clock.between if line.word == "CLOCK"]
        if found:
            offset = int(found[0].fields["offset_us"])
    return FaceLog(lines, sent, offset, clock.answer if clock is not None else None)


def views(log: FaceLog) -> list[Line]:
    """Give the SCREEN_VIEW lines."""
    return [line for line in log.lines if line.word == "SCREEN_VIEW"]


def at_us(line: Line) -> int:
    """Give the watch time of a diagnostic line with at_us or of an F or D line."""
    if kind_of(line.text) in ("F", "D"):
        return int(record_fields(line.text)[0])
    return int(line.fields.get("at_us", "0"))


def hh_mm(local_us: int) -> str:
    """Give the local time of day as HH:MM."""
    minutes = (local_us % DAY_US) // MINUTE_US
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def result(name: str, problems: list[str], detail: str = "") -> Check:
    """Make a check from a list of problems."""
    text = detail or f"{len(problems)} problems"
    return Check(name, not problems, text + (f", first: {problems[0]}" if problems else ""))


def sent_with(log: FaceLog, prefix: str) -> list[command_run.Sent]:
    """Give the commands that start with some text, in order."""
    return [s for s in log.sent if s.text.startswith(prefix)]


def schedules(log: FaceLog) -> list[tuple[command_run.Sent, int]]:
    """Give the FaceTest schedule commands and their minutes."""
    prefix = f"SCHEDULE,{DOSE_NAME},"
    out = []
    for s in sent_with(log, prefix):
        rest = s.text[len(prefix) :]
        if rest.isdigit():
            out.append((s, int(rest)))
    return out


def dose_local(log: FaceLog, minute: int, after: Line) -> int | None:
    """Give the first local time with the dose minute at or after a line's arrival on the watch."""
    if log.offset_us is None:
        return None
    ref = next((at_us(line) for line in log.lines[after.index :] if "at_us" in line.fields), None)
    if ref is None:
        return None
    local = ref + log.offset_us
    at = local // DAY_US * DAY_US + minute * MINUTE_US
    return at if at >= local else at + DAY_US


def f_lines(log: FaceLog) -> list[Line]:
    """Give the F lines."""
    return [line for line in log.lines if kind_of(line.text) == "F"]


def f_state(line: Line) -> int:
    """Give the state of an F line."""
    return int(record_fields(line.text)[1])


# ---------------------------------------------------------------- checks


def check_boot(log: FaceLog, version: int) -> Check:
    """Check one good B line and the format of every record line."""
    texts = [line.text for line in log.lines]
    boots = [t for t in texts if kind_of(t) == "B"]
    problems = []
    if len(boots) != 1:
        problems.append(f"{len(boots)} B lines")
    else:
        problems += record_run.boot_problems(boots[0], version)
    fmt = record_run.check_format(texts)
    if not fmt.passed:
        problems.append(fmt.detail)
    return result("one B line and the format", problems, boots[0] if boots else "")


def check_start(log: FaceLog) -> Check:
    """Check the SCREEN_START line."""
    starts = [line for line in log.lines if line.word == "SCREEN_START"]
    if not starts or not log.lines:
        return result("screen start", ["no SCREEN_START line"])
    s = starts[0]
    problems = []
    for key in ("display", "touch", "audio"):
        if s.fields.get(key) != "ok":
            problems.append(f"{key}={s.fields.get(key)}")
    if int(s.fields.get("internal_free", "0")) < INTERNAL_MIN:
        problems.append(f"internal_free={s.fields.get('internal_free')}")
    if s.seconds - log.lines[0].seconds > START_WITHIN_S:
        problems.append(f"SCREEN_START comes {s.seconds - log.lines[0].seconds:.1f} s after the B line")
    return result("screen start", problems, s.text)


def check_before_clock(log: FaceLog) -> Check:
    """Check the SCREEN_VIEW lines before the CLOCK command."""
    clock = sent_with(log, "CLOCK,")
    end = clock[0].line.index if clock else len(log.lines)
    before = [line for line in views(log) if line.index < end]
    problems = [f"line {v.index} gives time={v.fields.get('time')}" for v in before if v.fields.get("time") != "--:--"]
    if not before:
        problems.append("no SCREEN_VIEW line before CLOCK")
    elif before[0].fields.get("screen") != "home":
        problems.append(f"the first SCREEN_VIEW gives screen={before[0].fields.get('screen')}")
    return result("dashes before the clock", problems, f"{len(before)} SCREEN_VIEW lines")


def look_problems(all_views: list[Line], looks: Looks) -> list[str]:
    """Give each SCREEN_VIEW whose circle and colour differ from the looks of its face."""
    problems = []
    for v in all_views:
        look = looks.get(int(v.fields.get("face", "-1")))
        if look is None or (v.fields.get("circle"), v.fields.get("colour")) != look:
            problems.append(f"line {v.index} gives face={v.fields.get('face')} circle={v.fields.get('circle')} "
                            f"colour={v.fields.get('colour')}")
    return problems


def look_sets(version: int, live: bool) -> list[tuple[str, Looks]]:
    """Give the sets of looks that a log may show.

    A run with the watch must show the looks of the firmware now. A saved log
    may show any set of its version.
    """
    if live:
        return [("the looks of the firmware now", LOOKS)]
    return LOOKS_BY_VERSION.get(version, [("the looks of the firmware now", LOOKS)])


def check_faces(log: FaceLog, version: int, live: bool) -> Check:
    """Check a SCREEN_VIEW with the face of each F line and the look of each face.

    Every view must follow one set of looks of the version. The first set
    that fits names the looks in the report.
    """
    problems = []
    all_views = views(log)
    for f in f_lines(log):
        state = str(f_state(f))
        t = at_us(f)
        if not any(v.fields.get("face") == state and 0 <= at_us(v) - t <= VIEW_WITHIN_US for v in all_views):
            problems.append(f"no SCREEN_VIEW with face={state} within 1.1 s of {f.text}")
    sets = look_sets(version, live)
    fitting = next((name for name, looks in sets if not look_problems(all_views, looks)), None)
    if fitting is None:
        fitting = sets[0][0]
        problems += look_problems(all_views, sets[0][1])
    return result("the face of each F line", problems, f"{len(f_lines(log))} F lines, {fitting}")


def check_after_clock(log: FaceLog) -> Check:
    """Check the time of every SCREEN_VIEW after the CLOCK command's A line."""
    if log.offset_us is None or log.clock_answer is None:
        return result("time after the clock", ["no CLOCK command with a CLOCK line and an answer"])
    problems = []
    after = [v for v in views(log) if v.index > log.clock_answer.index]
    for v in after:
        local = at_us(v) + log.offset_us
        allowed = (hh_mm(local), hh_mm(local - MINUTE_US))
        if v.fields.get("time") not in allowed:
            problems.append(f"line {v.index} gives time={v.fields.get('time')}, want {allowed[0]}")
    return result("time after the clock", problems, f"{len(after)} SCREEN_VIEW lines")


def check_next(log: FaceLog) -> Check:
    """Check the next dose time after each schedule command."""
    problems = []
    found = schedules(log)
    if not found:
        problems.append("no schedule command")
    for s, minute in found:
        if s.answer is None or s.answer.text != "A,2,0":
            problems.append(f"{s.text} gets {s.answer.text if s.answer else 'no answer'}")
            continue
        want = f"{minute // 60:02d}:{minute % 60:02d}"
        ok = any(
            v.fields.get("next") == want and 0 <= v.seconds - s.answer.seconds <= SCHEDULE_VIEW_S
            for v in views(log)
            if v.index > s.answer.index
        )
        if not ok:
            problems.append(f"no SCREEN_VIEW with next={want} within 2 s of the answer to {s.text}")
    return result("next dose after each schedule", problems, f"{len(found)} schedules")


@dataclass
class Dose:
    """One scheduled dose and its lines."""

    local_us: int
    start: Line | None
    end: Line | None


def doses(log: FaceLog) -> list[Dose]:
    """Find each dose time and the F lines that start and end its due state."""
    out = []
    starts = [f for f in f_lines(log) if f_state(f) == 4]
    for s, minute in schedules(log):
        local = dose_local(log, minute, s.line)
        if local is None or log.offset_us is None:
            continue
        start = next((f for f in starts if at_us(f) + log.offset_us >= local and f.index > s.line.index), None)
        end = None
        if start is not None:
            end = next((f for f in f_lines(log) if f.index > start.index), None)
        out.append(Dose(local, start, end))
    return out


def check_first_dose(log: FaceLog) -> Check:
    """Check that the first dose becomes due with its tone and its view."""
    found = doses(log)
    if not found or found[0].start is None or log.offset_us is None:
        return result("first dose due", ["no F line with state 4 after the first schedule"])
    dose = found[0]
    start = dose.start
    assert start is not None
    late = at_us(start) + log.offset_us - dose.local_us
    problems = []
    if not 0 <= late <= DUE_LATE_US:
        problems.append(f"the F line comes {late} us after the dose time")
    tones = [line for line in log.lines if line.word == "TONE" and abs(line.seconds - start.seconds) <= 1.0]
    if not tones or tones[0].fields.get("enabled") != "1":
        problems.append("no TONE line with enabled=1 with the F line")
    else:
        play = [
            line for line in log.lines
            if line.word == "TONE_PLAY" and 0 <= line.seconds - tones[0].seconds <= TONE_PLAY_S
            and line.fields.get("kind") == "dose" and line.fields.get("tones") == "3"
        ]
        if not play:
            problems.append("no TONE_PLAY with kind=dose and tones=3 within 1 s of the TONE line")
    if not any(
        v.fields.get("face") == "4" and v.fields.get("due") == "1" and 0 <= at_us(v) - at_us(start) <= VIEW_WITHIN_US
        for v in views(log)
    ):
        problems.append("no SCREEN_VIEW with face=4 and due=1 within 1.1 s")
    return result("first dose due", problems, f"{late} us after the dose time")


def check_first_end(log: FaceLog) -> Check:
    """Check that the first due state ends after 15 minutes with its view and no second tone."""
    found = doses(log)
    if not found or found[0].start is None or found[0].end is None or log.offset_us is None:
        return result("first dose ends", ["no F line that ends the first due state"])
    dose = found[0]
    start, end = dose.start, dose.end
    assert start is not None and end is not None
    late = at_us(end) + log.offset_us - dose.local_us - DUE_US
    problems = []
    if not 0 <= late <= DUE_LATE_US:
        problems.append(f"the due state ends {late} us after the dose time plus 900 s")
    if not any(v.fields.get("due") == "0" and 0 <= at_us(v) - at_us(end) <= VIEW_WITHIN_US for v in views(log)):
        problems.append("no SCREEN_VIEW with due=0 within 1.1 s of the end")
    tone_off = sent_with(log, "TONE,0")
    stop = tone_off[0].line.index if tone_off else len(log.lines)
    tones = [line for line in log.lines if line.word == "TONE" and start.index - 5 <= line.index < stop]
    if len(tones) != 1:
        problems.append(f"{len(tones)} TONE lines for the first dose")
    return result("first dose ends", problems, f"{late} us after the dose time plus 900 s")


def check_second_dose(log: FaceLog) -> Check:
    """Check the second dose with the tone off, and the view after SESSION."""
    problems = []
    found = doses(log)
    tone_off = sent_with(log, "TONE,0")
    if len(found) < 2 or found[1].start is None:
        problems.append("no F line with state 4 after the second schedule")
    if not tone_off:
        problems.append("no TONE,0 command")
    else:
        after = [line for line in log.lines if line.index > tone_off[0].line.index]
        if not any(line.word == "TONE" and line.fields.get("enabled") == "0" for line in after):
            problems.append("no TONE line with enabled=0 after TONE,0")
        plays = [line for line in after if line.word == "TONE_PLAY"]
        if plays:
            problems.append(f"{len(plays)} TONE_PLAY lines after TONE,0")
    session = sent_with(log, "SESSION")
    if not session or session[0].answer is None or session[0].answer.text != "A,3,0":
        problems.append("no SESSION command with A,3,0")
    else:
        answer = session[0].answer
        if not any(
            v.fields.get("face") == "3" and v.fields.get("due") == "0"
            and 0 <= v.seconds - answer.seconds <= SESSION_VIEW_S
            for v in views(log) if v.index > answer.index
        ):
            problems.append("no SCREEN_VIEW with face=3 and due=0 within 2 s of A,3,0")
    return result("second dose and session", problems)


@dataclass
class ShareView:
    """The blocks and the share that the W lines give."""

    blocks: int
    hollow: str
    share: int


def share_from(log: FaceLog, end: int) -> ShareView:
    """Give the blocks and the share from the W lines before a place in the log.

    A window's time is t0 + 10000 * (100 * n + 399) microseconds from its
    stretch's S line, and the session starts at timer value 0."""
    t0: dict[int, int] = {}
    blocks: dict[int, list[int]] = {}
    tremor = still = 0
    for line in log.lines[:end]:
        kind = kind_of(line.text)
        if kind == "S" and record_run.is_record(line.text):
            fields = record_fields(line.text)
            t0[int(fields[0])] = int(fields[2])
        if kind != "W" or not record_run.is_record(line.text):
            continue
        stretch, window, code = record_fields(line.text)[:3]
        if not window or int(window) == 0 or int(window) % SHARE_EVERY != 0 or int(code) > 2:
            continue
        n = int(window)
        when = t0.get(int(stretch), 0) + 10_000 * (100 * n + 399)
        counts = blocks.setdefault(max(0, when) // BLOCK_US, [0, 0])
        if int(code) in (0, 1):
            counts[1] += 1
            still += 1
        if int(code) == 0:
            counts[0] += 1
            tremor += 1
    # The share keeps every block from block 0 to the latest, at most 12.
    last = max(blocks, default=-1)
    numbers = list(range(max(0, last - BLOCKS_KEPT + 1), last + 1))
    hollow = "".join("1" if blocks.get(b, [0, 0])[1] < HOLLOW_BELOW else "0" for b in numbers)
    # Halves round up on whole numbers, as core/view.c does.
    share = (200 * tremor + still) // (2 * still) if still else -1
    return ShareView(len(numbers), hollow or "none", share)


def check_blocks(log: FaceLog) -> Check:
    """Check the blocks and the share of the last SCREEN_VIEW before SESSION."""
    session = sent_with(log, "SESSION")
    end = session[0].line.index if session else len(log.lines)
    before = [v for v in views(log) if v.index < end]
    if not before:
        return result("blocks and share", ["no SCREEN_VIEW before SESSION"])
    last = before[-1]
    got = (int(last.fields.get("blocks", "-1")), last.fields.get("hollow"), int(last.fields.get("share", "-2")))
    w_before = [line.index for line in log.lines[: last.index] if kind_of(line.text) == "W"]
    wants = [share_from(log, last.index)]
    if w_before:
        wants.append(share_from(log, w_before[-1]))
    problems = []
    if not any(got == (w.blocks, w.hollow, w.share) for w in wants):
        problems.append(f"the last SCREEN_VIEW gives {got}, the W lines give {(wants[0].blocks, wants[0].hollow, wants[0].share)}")
    first_hollow = next(
        (v for v in before if v.fields.get("blocks") == "1" and v.fields.get("hollow", "")[:1] == "1"), None
    )
    if first_hollow is None:
        problems.append("no SCREEN_VIEW with blocks=1 and block 0 hollow")
    elif not any(v.index > first_hollow.index and v.fields.get("hollow", "")[:1] == "0" for v in before):
        problems.append("no later SCREEN_VIEW with block 0 not hollow")
    return result("blocks and share", problems, f"last SCREEN_VIEW gives {got}")


def check_minutes(log: FaceLog) -> Check:
    """Check the minute lines and that no SCREEN_ERROR line comes."""
    problems = []
    for line in log.lines:
        f = line.fields
        if line.word == "SCREEN_MINUTE":
            if int(f.get("updates", "0")) < UPDATES_MIN or f.get("width_mismatch") != "0" \
                    or int(f.get("internal_min", "0")) < INTERNAL_MIN or int(f.get("stack_free", "0")) < STACK_MIN:
                problems.append(line.text)
        elif line.word == "STATE_MINUTE" and f.get("screen_drops") != "0":
            problems.append(line.text)
        elif line.word == "USB_MINUTE" and (f.get("line_drops") != "0" or f.get("port_drops") != "0"):
            problems.append(line.text)
        elif line.word == "SCREEN_ERROR":
            problems.append(line.text)
    minutes = sum(1 for line in log.lines if line.word == "SCREEN_MINUTE")
    if minutes == 0:
        problems.append("no SCREEN_MINUTE line")
    return result("minute lines", problems, f"{minutes} SCREEN_MINUTE lines")


def check_untouched(log: FaceLog) -> Check:
    """Check that the log holds no D, DOSE, DOSE_REFUSED, TOUCH, or BUTTON line."""
    found = [line.text for line in log.lines
             if kind_of(line.text) == "D" or line.word in ("DOSE", "DOSE_REFUSED", "TOUCH", "BUTTON")]
    return result("nobody touched the watch", [f"line {t}" for t in found], f"{len(found)} lines")


def check_settings(log: FaceLog) -> Check:
    """Check that the last SETTINGS line gives the settings of the boot."""
    settings = [line.fields for line in log.lines if line.word == "SETTINGS"]
    boot = next((f for f in settings if f.get("source") == "boot"), None)
    if boot is None or not settings:
        return result("settings put back", ["no SETTINGS line with source=boot"])
    keys = ("tone", "times", "name")
    last = settings[-1]
    problems = [f"{k}={last.get(k)}, boot gives {boot.get(k)}" for k in keys if last.get(k) != boot.get(k)]
    return result("settings put back", problems, " ".join(f"{k}={last.get(k)}" for k in keys))


def judge(log: FaceLog, version: int, live: bool) -> list[Check]:
    """Give the result of every pass check by the rules of one firmware version."""
    return [
        check_boot(log, version),
        check_start(log),
        check_before_clock(log),
        check_faces(log, version, live),
        check_after_clock(log),
        check_next(log),
        check_first_dose(log),
        check_first_end(log),
        check_second_dose(log),
        check_blocks(log),
        check_minutes(log),
        check_untouched(log),
        check_settings(log),
    ]


def measurements(log: FaceLog) -> list[str]:
    """Give the measurements as report lines."""
    out = []
    start = next((line for line in log.lines if line.word == "SCREEN_START"), None)
    if start is not None:
        out.append(f"- SCREEN_START gives internal_free={start.fields.get('internal_free')} and "
                   f"internal_largest={start.fields.get('internal_largest')}.")
    for kind, key in (("SCREEN_MINUTE", "stack_free"), ("SCREEN_MINUTE", "internal_min"),
                      ("STATE_MINUTE", "stack_free"), ("USB_MINUTE", "stack_free")):
        values = [line.fields.get(key, "?") for line in log.lines if line.word == kind]
        if values:
            out.append(f"- {kind} gives {key} from {min(values, key=int)} to {max(values, key=int)} bytes.")
    for n, dose in enumerate(doses(log)):
        if dose.start is not None and log.offset_us is not None:
            late = at_us(dose.start) + log.offset_us - dose.local_us
            out.append(f"- Dose {n + 1} became due {late / 1e6:.3f} seconds after its time.")
    out.append(f"- The log holds {len(views(log))} SCREEN_VIEW lines.")
    return out


def write_report(path: Path, checks: list[Check], measured: list[str], notes: list[str]) -> None:
    """Write the report with the notes, the checks, and the measurements."""
    lines = ["# Face run", "", *notes, "", "## Pass checks", ""]
    lines += [f"- {'PASS' if c.passed else 'FAIL'}: {c.name}. {c.detail}" for c in checks]
    lines += ["", "## Measurements", ""] + measured
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run or judge the face run and give the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log-only", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.log_only:
        run(args.port, args.log)
    saved = record_run.load_log(args.log)
    live = not args.log_only
    try:
        version = record_run.judged_version([e.text for e in saved.entries], live, KNOWN_VERSIONS)
    except record_run.UnknownVersion as error:
        LOG.error("The judge refuses the log: %s.", error)
        return 1
    log = parse(saved.entries)
    checks = judge(log, version, live)
    write_report(args.report, checks, measurements(log), record_run.report_notes(saved, version, live))
    for check in checks:
        LOG.info("%s: %s. %s", "PASS" if check.passed else "FAIL", check.name, check.detail)
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
