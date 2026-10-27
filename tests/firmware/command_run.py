"""Send the four commands to the watch and judge the log.

Runs check 9 of specs/features/09-usb-recording/validation.md. The watch
lies still on a table on USB power with firmware/ flashed. In order, the
script sends nine bad commands, turns the tone off, sets a dose time about 4
minutes ahead, restarts the watch, sets the clock, waits for the dose to
become due and to end, starts a new session, and puts the settings of the
first boot back. It saves every line with the laptop's time in seconds as gzip
text. Each command it sends and each reset go into the log as lines that start
with "> ". It runs with the ESP-IDF Python, which has pyserial, and takes
about 23 minutes.

    caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/command_run.py

The judge reads the log alone, so --log-only gives the same result. It exits
with code 0 only when every pass check holds.
"""
from __future__ import annotations

import argparse
import gzip
import logging
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import record_run  # noqa: E402
from record_run import Entry, kind_of, read_log, record_fields  # noqa: E402
from table_run import Check, fields_of  # noqa: E402

LOG = logging.getLogger("command_run")

REPO = HERE.parents[1]
DEFAULT_PORT = "/dev/cu.usbmodem101"
DEFAULT_LOG = REPO / "tests" / "firmware" / "command_log.txt.gz"
DEFAULT_REPORT = REPO / "tests" / "firmware" / "command_report.md"

RESET = "RESET"
# The nine bad commands and the A line each must get, in the order sent.
BAD_COMMANDS = (
    ("HELLO", "A,0,1"),
    ("TONE", "A,4,2"),
    ("TONE,2", "A,4,3"),
    ("CLOCK,abc,0", "A,1,2"),
    ("CLOCK,1761206400000000,900", "A,1,3"),
    ("SCHEDULE,Levodopa,1440", "A,2,3"),
    ("SCHEDULE,Levodopa,480,480", "A,2,3"),
    ("SESSION,1", "A,3,2"),
    ("X" * 200, "A,0,2"),
)
DOSE_NAME = "TestDose"
# The dose time lies at least this long after the schedule command.
LEAD_S = 240
# The script waits this long after the dose time, and after its end.
DUE_WAIT_S = 10
DUE_US = 900_000_000
# The script waits this long for the answer to each command.
ANSWER_WAIT_S = 5.0
# The script waits this long for the first boot's face and the second boot's
# first minute line, and for the minute line after the session command.
BOOT_WAIT_S = 120.0
MINUTE_WAIT_S = 75.0
DAY_US = 86_400_000_000
MINUTE_US = 60_000_000
# Pass limits.
DUE_LATE_US = 1_100_000
CLOCK_LIMIT_US = 1_000_000
SESSION_ANSWERS_MAX = 61


def restore_commands(fields: dict[str, str]) -> list[str]:
    """Give the SCHEDULE and TONE commands that put back the settings of a SETTINGS line."""
    name = fields.get("name", "")
    times = fields.get("times", "none")
    parts = ["SCHEDULE"]
    if name or times != "none":
        parts.append(name)
    if times != "none":
        parts.append(times)
    return [",".join(parts), f"TONE,{fields.get('tone', '1')}"]


def next_dose_time(now: datetime) -> datetime:
    """Give the local time LEAD_S seconds after now, rounded up to the next whole minute."""
    target = now + timedelta(seconds=LEAD_S)
    whole = target.replace(second=0, microsecond=0)
    return whole if whole == target else whole + timedelta(minutes=1)


@dataclass
class Runner:
    """The port and the open log of a run."""

    port: str
    out: Any
    started: float
    ser: Any
    boot_settings: dict[str, str] | None = None


def make_runner(port: str, out: Any) -> Runner:
    """Open the port with no reset and start the clock of the log."""
    return Runner(port, out, time.monotonic(), record_run.open_port(port, reset=False))


def note(r: Runner, text: str) -> None:
    """Write one of the script's own lines."""
    record_run.write_entry(r.out, r.started, f"> {text}")


def read(r: Runner) -> str | None:
    """Read and save one line, or give None when nothing came."""
    r.ser, text = record_run.read_line(r.ser, r.port)
    if text is None:
        return None
    record_run.write_entry(r.out, r.started, text)
    if text.startswith("SETTINGS ") and r.boot_settings is None:
        r.boot_settings = fields_of(text)
    return text


def read_until(r: Runner, done: Callable[[str], bool], seconds: float) -> bool:
    """Read until a line meets the test or the time passes."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        text = read(r)
        if text is not None and done(text):
            return True
    return False


def read_until_epoch(r: Runner, epoch: float) -> None:
    """Read until the laptop's clock passes a time in seconds since 1970."""
    while time.time() < epoch:
        read(r)


def reset_watch(r: Runner) -> None:
    """Reset the watch with a pulse on RTS."""
    note(r, RESET)
    r.ser.rts = True
    time.sleep(0.1)
    r.ser.rts = False


def send(r: Runner, text: str) -> None:
    """Send one command and read until its A line arrives or ANSWER_WAIT_S passes."""
    note(r, text)
    r.ser.write((text + "\n").encode())
    read_until(r, lambda line: kind_of(line) == "A", ANSWER_WAIT_S)


def is_face(state: int) -> Callable[[str], bool]:
    """Give a test for a FACE line with one state."""
    return lambda text: text.startswith("FACE ") and fields_of(text).get("state") == str(state)


def is_minute(minute: int | None) -> Callable[[str], bool]:
    """Give a test for a STATE_MINUTE line, of one minute when minute is given."""
    return lambda text: text.startswith("STATE_MINUTE ") and (
        minute is None or fields_of(text).get("minute") == str(minute)
    )


def run(port: str, log_path: Path) -> None:
    """Run every step on the watch."""
    with gzip.open(log_path, "wt") as out:
        r = make_runner(port, out)
        reset_watch(r)
        read_until(r, is_face(1), BOOT_WAIT_S)
        boot_settings = r.boot_settings or {}
        for text, _ in BAD_COMMANDS:
            send(r, text)
        send(r, "TONE,0")
        dose_time = next_dose_time(datetime.now().astimezone())
        minute = dose_time.hour * 60 + dose_time.minute
        send(r, f"SCHEDULE,{DOSE_NAME},{minute}")
        reset_watch(r)
        read_until(r, is_minute(1), BOOT_WAIT_S)
        offset = datetime.now().astimezone().utcoffset() or timedelta(0)
        send(r, f"CLOCK,{time.time_ns() // 1000},{int(offset.total_seconds()) // 60}")
        read_until_epoch(r, dose_time.timestamp() + DUE_WAIT_S)
        read_until_epoch(r, dose_time.timestamp() + DUE_US / 1e6 + DUE_WAIT_S)
        send(r, "SESSION")
        read_until(r, is_minute(None), MINUTE_WAIT_S)
        send(r, "TONE,1")
        for text in restore_commands(boot_settings):
            send(r, text)
        r.ser.close()


@dataclass
class Line:
    """One line of the log with its place, its first word, and its fields."""

    index: int
    seconds: float
    text: str
    word: str
    fields: dict[str, str]


@dataclass
class Sent:
    """One command, its A line, and the lines between them."""

    text: str
    line: Line
    answer: Line | None
    between: list[Line]


@dataclass
class Log:
    """The parts of a command log that the checks use."""

    lines: list[Line]
    boots: list[list[Line]]
    sent: list[Sent]


def sent_from(lines: list[Line], line: Line) -> Sent:
    """Find the A line of one command before the next line of the script."""
    between: list[Line] = []
    for later in lines[line.index + 1 :]:
        if later.text.startswith("> "):
            break
        if kind_of(later.text) == "A":
            return Sent(line.text[2:], line, later, between)
        between.append(later)
    return Sent(line.text[2:], line, None, between)


def parse_log(entries: list[Entry]) -> Log:
    """Split the log into boots at each reset and find each command's answer.
    Each boot starts at its first B line, so the ROM text is left out."""
    lines = [Line(i, e.seconds, e.text, e.text.split(" ", 1)[0], fields_of(e.text)) for i, e in enumerate(entries)]
    resets = [line.index for line in lines if line.text == f"> {RESET}"]
    boots: list[list[Line]] = []
    for n, start in enumerate(resets):
        end = resets[n + 1] if n + 1 < len(resets) else len(lines)
        part = lines[start + 1 : end]
        first_b = next((i for i, line in enumerate(part) if kind_of(line.text) == "B"), len(part))
        boots.append(part[first_b:])
    sent = [sent_from(lines, line) for line in lines if line.text.startswith("> ") and line.text != f"> {RESET}"]
    return Log(lines, boots, sent)


def boot(log: Log, n: int) -> list[Line]:
    """Give the lines of boot n from its B line on, or an empty list."""
    return log.boots[n] if n < len(log.boots) else []


def answer_of(sent: Sent | None) -> str:
    """Give the text of a command's A line, or "none"."""
    return sent.answer.text if sent is not None and sent.answer is not None else "none"


def settings_in(sent: Sent, source: str) -> list[dict[str, str]]:
    """Give the SETTINGS lines of one source between a command and its answer."""
    return [line.fields for line in sent.between if line.word == "SETTINGS" and line.fields.get("source") == source]


def find_sent(log: Log, text: str, after: int = -1) -> Sent | None:
    """Give the first command with some text after a place in the log."""
    return next((s for s in log.sent if s.text == text and s.line.index > after), None)


def boot_check(lines: list[Line], name: str) -> tuple[list[str], str]:
    """Check one boot's B line and START line. Give the problems and the B line."""
    boots = [line for line in lines if kind_of(line.text) == "B"]
    starts = [line for line in lines if line.word == "START"]
    problems = []
    if len(boots) != 1 or len(starts) != 1:
        problems.append(f"{name} has {len(boots)} B lines and {len(starts)} START lines")
        return problems, boots[0].text if boots else ""
    problems += [f"{name}: {p}" for p in record_run.boot_problems(boots[0].text)]
    if boots[0].index > starts[0].index:
        problems.append(f"{name} has its B line after START")
    return problems, boots[0].text


def result(name: str, problems: list[str], detail: str = "") -> Check:
    """Make a check from a list of problems."""
    text = detail or f"{len(problems)} problems"
    return Check(name, not problems, text + (f", first: {problems[0]}" if problems else ""))


def check_boot1(log: Log) -> Check:
    """Check boot 1's B line and its SETTINGS line."""
    lines = boot(log, 0)
    problems, b_line = boot_check(lines, "boot 1")
    settings = [line for line in lines if line.word == "SETTINGS" and line.fields.get("source") == "boot"]
    if len(settings) != 1:
        problems.append(f"boot 1 has {len(settings)} SETTINGS lines with source=boot")
    return result("boot 1", problems, b_line)


def check_bad_commands(log: Log) -> Check:
    """Check the nine bad commands and their answers in order."""
    problems = []
    sent = log.sent[: len(BAD_COMMANDS)]
    if [s.text for s in sent] != [text for text, _ in BAD_COMMANDS]:
        return result("nine bad commands", ["the first nine commands are not the bad commands"])
    for s, (text, want) in zip(sent, BAD_COMMANDS):
        if answer_of(s) != want:
            problems.append(f"{text[:20]} gets {answer_of(s)}, want {want}")
    last = sent[-1].answer.index if sent[-1].answer is not None else len(log.lines)
    for line in log.lines[:last]:
        if line.word in ("CLOCK", "SESSION") or (line.word == "SETTINGS" and line.fields.get("source") == "command"):
            problems.append(f"line {line.index} is {line.text}")
    return result("nine bad commands", problems)


def check_tone_off(log: Log) -> Check:
    """Check that TONE,0 turns the tone off and stores it."""
    s = find_sent(log, "TONE,0")
    if s is None:
        return result("tone off", ["no TONE,0 command"])
    settings = settings_in(s, "command")
    ok = answer_of(s) == "A,4,0" and any(f.get("store") == "ok" and f.get("tone") == "0" for f in settings)
    return Check("tone off", ok, f"answer {answer_of(s)}, SETTINGS {settings}")


def schedule_sent(log: Log) -> tuple[Sent | None, int | None]:
    """Give the schedule command of the dose and its minute."""
    prefix = f"SCHEDULE,{DOSE_NAME},"
    s = next((s for s in log.sent if s.text.startswith(prefix)), None)
    if s is None or not s.text[len(prefix) :].isdigit():
        return None, None
    return s, int(s.text[len(prefix) :])


def check_schedule(log: Log) -> Check:
    """Check that the schedule command sets and stores the dose time."""
    s, minute = schedule_sent(log)
    if s is None:
        return result("schedule", ["no schedule command"])
    settings = settings_in(s, "command")
    ok = answer_of(s) == "A,2,0" and any(
        f.get("store") == "ok" and f.get("times") == str(minute) and f.get("name") == DOSE_NAME for f in settings
    )
    return Check("schedule", ok, f"{s.text} gets {answer_of(s)}, SETTINGS {settings}")


def check_restart(log: Log) -> Check:
    """Check that the restart kept the schedule and the tone and left the clock unset."""
    lines = boot(log, 1)
    problems, b_line = boot_check(lines, "boot 2")
    first = next((line.text for line in boot(log, 0) if kind_of(line.text) == "B"), "")
    if b_line and first and record_fields(b_line)[0] == record_fields(first)[0]:
        problems.append("boot 2 has the boot ID of boot 1")
    _, minute = schedule_sent(log)
    settings = [line.fields for line in lines if line.word == "SETTINGS" and line.fields.get("source") == "boot"]
    want = {"store": "ok", "tone": "0", "times": str(minute), "name": DOSE_NAME}
    if len(settings) != 1 or any(settings[0].get(k) != v for k, v in want.items()):
        problems.append(f"boot 2 gives SETTINGS {settings}")
    minute1 = next(
        (line.fields for line in lines if line.word == "STATE_MINUTE" and line.fields.get("minute") == "1"), {}
    )
    if minute1.get("clock") != "0" or minute1.get("schedule") != "1":
        problems.append(f"STATE_MINUTE minute 1 gives clock={minute1.get('clock')} schedule={minute1.get('schedule')}")
    return result("restart keeps the settings", problems, b_line)


@dataclass
class Clock:
    """The CLOCK command of boot 2 and what the watch made of it."""

    sent: Sent
    utc_us: int
    offset_min: int
    offset_us: int
    local_us: int


def clock_of(log: Log) -> Clock | None:
    """Give boot 2's CLOCK command and its CLOCK line."""
    lines = boot(log, 1)
    if not lines:
        return None
    s = next((s for s in log.sent if s.text.startswith("CLOCK,") and s.line.index > lines[0].index), None)
    if s is None:
        return None
    clock_lines = [line.fields for line in s.between if line.word == "CLOCK"]
    if len(clock_lines) != 1:
        return None
    parts = s.text.split(",")
    found = clock_lines[0]
    return Clock(s, int(parts[1]), int(parts[2]), int(found["offset_us"]), int(found["local_us"]))


def check_clock(log: Log) -> Check:
    """Check the CLOCK command, its CLOCK line, and the next minute line."""
    clock = clock_of(log)
    if clock is None:
        return result("clock", ["no CLOCK command with one CLOCK line in boot 2"])
    problems = []
    if answer_of(clock.sent) != "A,1,0":
        problems.append(f"the answer is {answer_of(clock.sent)}")
    diff = clock.local_us - (clock.utc_us + clock.offset_min * MINUTE_US)
    if abs(diff) > CLOCK_LIMIT_US:
        problems.append(f"local_us is {diff} us from the command's time")
    after = clock.sent.answer.index if clock.sent.answer is not None else clock.sent.line.index
    minute = next((line.fields for line in log.lines[after:] if line.word == "STATE_MINUTE"), {})
    if minute.get("clock") != "1":
        problems.append(f"the next STATE_MINUTE gives clock={minute.get('clock')}")
    return result("clock", problems, f"difference {diff} us")


def dose_local_us(clock: Clock, minute: int) -> int:
    """Give the first local time at or after the clock command with the dose's minute of the day."""
    day = clock.local_us // DAY_US
    at = day * DAY_US + minute * MINUTE_US
    return at if at >= clock.local_us else at + DAY_US


@dataclass
class Due:
    """The F lines that start and end the due dose in boot 2."""

    t_us: int
    offset_us: int
    start: list[Line]
    end: Line | None


def due_of(log: Log) -> Due | None:
    """Find the dose time T and the F lines of the due dose."""
    clock = clock_of(log)
    _, minute = schedule_sent(log)
    if clock is None or minute is None:
        return None
    lines = boot(log, 1)
    starts = [line for line in lines if kind_of(line.text) == "F" and record_fields(line.text)[1] == "4"]
    end = None
    if len(starts) == 1:
        end = next((line for line in lines if kind_of(line.text) == "F" and line.index > starts[0].index), None)
    return Due(dose_local_us(clock, minute), clock.offset_us, starts, end)


def f_local(line: Line, offset_us: int) -> int:
    """Give the local time of an F line."""
    return int(record_fields(line.text)[0]) + offset_us


def check_due(log: Log) -> Check:
    """Check the F line that starts the due dose and its TONE line."""
    due = due_of(log)
    if due is None:
        return result("dose becomes due", ["no clock or no schedule"])
    if len(due.start) != 1:
        return result("dose becomes due", [f"boot 2 has {len(due.start)} F lines with state 4"])
    start = due.start[0]
    late = f_local(start, due.offset_us) - due.t_us
    problems = []
    if not 0 <= late <= DUE_LATE_US:
        problems.append(f"the F line comes {late} us after T")
    lines = boot(log, 1)
    answers = [line.index for line in lines if line.word == "ANSWER"]
    before = max((i for i in answers if i < start.index), default=-1)
    after = min((i for i in answers if i > start.index), default=len(log.lines))
    tones = [line for line in lines if line.word == "TONE"]
    if len(tones) != 1 or tones[0].fields.get("enabled") != "0" or not before < tones[0].index < after:
        problems.append(f"boot 2 has the TONE lines {[t.text for t in tones]}")
    return result("dose becomes due", problems, f"{late} us after T")


def check_due_end(log: Log) -> Check:
    """Check the due state and the F line that ends it."""
    due = due_of(log)
    if due is None or len(due.start) != 1 or due.end is None:
        return result("due dose ends", ["no due dose with an end"])
    start = due.start[0]
    late = f_local(due.end, due.offset_us) - due.t_us - DUE_US
    problems = []
    if record_fields(due.end.text)[1] != "1":
        problems.append(f"the F line after the due dose is {due.end.text}")
    if not 0 <= late <= DUE_LATE_US:
        problems.append(f"the due dose ends {late} us after T + 900 s")
    for line in log.lines[start.index : due.end.index]:
        if line.word == "ANSWER" and line.fields.get("face") != "4":
            problems.append(f"line {line.index} gives face={line.fields.get('face')}")
        if line.word == "STATE_MINUTE" and line.fields.get("due") != "1":
            problems.append(f"line {line.index} gives due={line.fields.get('due')}")
    return result("due dose ends", problems, f"{late} us after T + 900 s")


def check_session(log: Log) -> Check:
    """Check that SESSION starts a new session."""
    s = find_sent(log, "SESSION")
    if s is None:
        return result("new session", ["no SESSION command"])
    problems = []
    if answer_of(s) != "A,3,0":
        problems.append(f"the answer is {answer_of(s)}")
    session = next((line for line in s.between if line.word == "SESSION"), None)
    faces = [line for line in s.between if kind_of(line.text) == "F" and record_fields(line.text)[1] == "3"]
    if session is None or session.fields.get("changed") != "1" or not faces:
        problems.append("no SESSION line with changed=1 and F line with state 3 before the answer")
        return result("new session", problems)
    after = log.lines[session.index + 1 :]
    answers = [line for line in after if line.word == "ANSWER"][:3]
    if len(answers) < 3 or any(a.fields.get("code") != "1" for a in answers[:2]):
        problems.append("the first two answers after SESSION do not have code 1")
    else:
        ones = [
            line
            for line in after
            if kind_of(line.text) == "F" and record_fields(line.text)[1] == "1"
            and answers[1].index < line.index < answers[2].index
        ]
        if not ones:
            problems.append("no F line with state 1 between the second and the third answer")
    first_minute = next((line.fields for line in after if line.word == "STATE_MINUTE"), {})
    last_minute = next(
        (line.fields for line in reversed(log.lines[: session.index]) if line.word == "STATE_MINUTE"), {}
    )
    if int(first_minute.get("answers", "-1")) > SESSION_ANSWERS_MAX or first_minute.get("doses") != "0":
        problems.append(f"the first STATE_MINUTE after SESSION gives {first_minute}")
    if int(last_minute.get("answers", "0")) <= SESSION_ANSWERS_MAX:
        problems.append(f"the last STATE_MINUTE before SESSION gives answers={last_minute.get('answers')}")
    return result("new session", problems)


def check_tone_on(log: Log) -> Check:
    """Check that TONE,1 turns the tone on."""
    session = find_sent(log, "SESSION")
    s = find_sent(log, "TONE,1", session.line.index if session is not None else -1)
    if s is None:
        return result("tone on", ["no TONE,1 command after SESSION"])
    settings = settings_in(s, "command")
    ok = answer_of(s) == "A,4,0" and any(f.get("tone") == "1" for f in settings)
    return Check("tone on", ok, f"answer {answer_of(s)}, SETTINGS {settings}")


def check_restore(log: Log) -> Check:
    """Check the commands that put back the settings of boot 1."""
    boot_settings = next(
        (line.fields for line in boot(log, 0) if line.word == "SETTINGS" and line.fields.get("source") == "boot"), None
    )
    if boot_settings is None:
        return result("settings put back", ["boot 1 has no SETTINGS line"])
    want = restore_commands(boot_settings)
    sent = log.sent[-len(want) :]
    got = [(s.text, answer_of(s)) for s in sent]
    ok = got == list(zip(want, ("A,2,0", "A,4,0")))
    return Check("settings put back", ok, f"commands and answers {got}, want {want}")


def check_format(log: Log) -> Check:
    """Check the format of both boots and one START line in each."""
    problems = []
    if len(log.boots) != 2:
        problems.append(f"the log holds {len(log.boots)} resets")
    for n, lines in enumerate(log.boots):
        texts = [line.text for line in lines]
        check = record_run.check_format(texts)
        if not check.passed:
            problems.append(f"boot {n + 1}: {check.detail}")
        starts = sum(1 for text in texts if text.startswith("START "))
        if starts != 1:
            problems.append(f"boot {n + 1} has {starts} START lines")
    return result("format in both boots", problems)


def judge(log: Log) -> list[Check]:
    """Give the result of every pass check."""
    return [
        check_boot1(log),
        check_bad_commands(log),
        check_tone_off(log),
        check_schedule(log),
        check_restart(log),
        check_clock(log),
        check_due(log),
        check_due_end(log),
        check_session(log),
        check_tone_on(log),
        check_restore(log),
        check_format(log),
    ]


def measurements(log: Log) -> list[str]:
    """Give the measurements as report lines."""
    out = []
    due = due_of(log)
    if due is not None and len(due.start) == 1:
        late = f_local(due.start[0], due.offset_us) - due.t_us
        out.append(f"- The due F line came {late / 1e6:.3f} seconds after T.")
        if due.end is not None:
            late = f_local(due.end, due.offset_us) - due.t_us - DUE_US
            out.append(f"- The F line that ended the due state came {late / 1e6:.3f} seconds after T + 900 seconds.")
    clock = clock_of(log)
    if clock is not None:
        diff = clock.local_us - (clock.utc_us + clock.offset_min * MINUTE_US)
        out.append(f"- The clock difference was {diff} microseconds.")
    b_line = next((line.text for line in boot(log, 1) if kind_of(line.text) == "B"), "")
    if b_line:
        out.append(f"- Boot 2's reset cause was {record_fields(b_line)[1]}.")
    waits = [(s.text[:24], s.answer.seconds - s.line.seconds) for s in log.sent if s.answer is not None]
    if waits:
        times = [w for _, w in waits]
        out.append(
            f"- The time from a command to its answer on the laptop was median {statistics.median(times):.3f} and "
            f"maximum {max(times):.3f} seconds over {len(times)} commands."
        )
    for kind in ("STATE_MINUTE", "USB_MINUTE"):
        free = [line.fields.get("stack_free", "?") for line in log.lines if line.word == kind]
        out.append(f"- {kind} gives the free stack in bytes as {', '.join(free) or 'none'}.")
    return out


def write_report(path: Path, checks: list[Check], measured: list[str]) -> None:
    """Write the report with the checks and the measurements."""
    lines = ["# Command run", "", "## Pass checks", ""]
    lines += [f"- {'PASS' if c.passed else 'FAIL'}: {c.name}. {c.detail}" for c in checks]
    lines += ["", "## Measurements", ""] + measured
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run or judge the command run and give the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--port", default=DEFAULT_PORT)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--log-only", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not args.log_only:
        run(args.port, args.log)
    log = parse_log(read_log(args.log))
    checks = judge(log)
    write_report(args.report, checks, measurements(log))
    for check in checks:
        LOG.info("%s: %s. %s", "PASS" if check.passed else "FAIL", check.name, check.detail)
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
