"""Guide a person through the face's taps and BOOT presses and judge the log.

Runs check 13 of specs/features/11-watch-face/validation.md. The watch lies
on a table on USB power with firmware/ flashed. The script opens the port with
no reset, sets the dose clock, and shows each step to the person. It marks
each step in the log with a line "> STEP n", waits for the lines that the step
needs or 60 seconds, and goes on. Step 8 waits up to 320 seconds, because the
screen goes back to Home after 5 minutes. At the end it puts the starting
schedule and tone back. It saves every line with the
laptop's time in seconds as gzip text, and each command it sends goes into the
log as a line that starts with "> ". It runs with the ESP-IDF Python, which
has pyserial, and takes about 12 minutes.

    ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/tap_run.py

The judge reads the log alone, so --log-only gives the same result. It exits
with code 0 only when every pass check holds.
"""
from __future__ import annotations

import argparse
import gzip
import logging
import re
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import command_run  # noqa: E402
import record_run  # noqa: E402
from command_run import Line, Runner  # noqa: E402
from record_run import Entry, kind_of, read_log, record_fields  # noqa: E402
from table_run import Check, fields_of  # noqa: E402

LOG = logging.getLogger("tap_run")

REPO = HERE.parents[1]
DEFAULT_PORT = "/dev/cu.usbmodem101"
DEFAULT_LOG = REPO / "tests" / "firmware" / "tap_log.txt.gz"
DEFAULT_REPORT = REPO / "tests" / "firmware" / "tap_report.md"
REPLAY = REPO / "build" / "core" / "replay"

STEP = "STEP"
DOSE_NAME = "TapTest"
# The dose time lies at least this long after the schedule command.
LEAD_S = 90
# The script waits this long for the lines of a step, and longer in step 8
# for the screen to go back to Home.
STEP_WAIT_S = 60.0
IDLE_WAIT_S = 320.0
# The script reads this long after a step's lines, so late lines join the step.
SETTLE_S = 2.0
FIRST_READ_S = 2.0
DAY_US = 86_400_000_000
MINUTE_US = 60_000_000
# Pass limits.
WITHIN_S = 1.0
NO_TONE_S = 2.0
LOGGED_MIN_US = 2_800_000
LOGGED_MAX_US = 3_200_000
IDLE_MIN_US = 298_000_000
IDLE_MAX_US = 302_000_000
FACE_BACK_US = 1_100_000
STEP_COUNT = 9

Test = Callable[[str], bool]


def prompt(text: str) -> None:
    """Show one step's instruction to the person. This is the only print in the file."""
    print(f"\n>>> {text}", flush=True)


def dose_minute(now: datetime) -> int:
    """Give the minute of the local day of the next whole minute at least LEAD_S seconds after now."""
    target = now + timedelta(seconds=LEAD_S)
    whole = target.replace(second=0, microsecond=0)
    if whole != target:
        whole += timedelta(minutes=1)
    return whole.hour * 60 + whole.minute


def word_is(word: str, **want: str) -> Test:
    """Give a test for a diagnostic line with a first word and some field values."""

    def test(text: str) -> bool:
        if text.split(" ", 1)[0] != word:
            return False
        fields = fields_of(text)
        return all(fields.get(k) == v for k, v in want.items())

    return test


def letter_is(letter: str) -> Test:
    """Give a test for a record line of one letter."""
    return lambda text: kind_of(text) == letter


def is_due_face(text: str) -> bool:
    """Tell an F line with the Dose due state."""
    return kind_of(text) == "F" and record_run.is_record(text) and record_fields(text)[1] == "4"


def wait_for(r: Runner, needs: list[Test], seconds: float) -> None:
    """Read until each test has met its own line or the time passes."""
    left = list(needs)
    end = time.monotonic() + seconds
    while left and time.monotonic() < end:
        text = command_run.read(r)
        if text is None:
            continue
        hit = next((i for i, test in enumerate(left) if test(text)), None)
        if hit is not None:
            left.pop(hit)


def read_for(r: Runner, seconds: float) -> None:
    """Read and save lines for a fixed time."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        command_run.read(r)


def step(r: Runner, n: int, text: str) -> None:
    """Mark the start of a step in the log and show its instruction."""
    command_run.note(r, f"{STEP} {n}")
    prompt(f"Step {n}. {text}")


def run(port: str, log_path: Path) -> None:
    """Run every step with the person."""
    with gzip.open(log_path, "wt") as out:
        r = command_run.make_runner(port, out)
        read_for(r, FIRST_READ_S)
        if r.boot_settings is None:
            # The watch writes a SETTINGS line only at boot and for a command.
            command_run.send(r, "TONE,1")
        boot_settings = dict(r.boot_settings or {})
        offset = datetime.now().astimezone().utcoffset() or timedelta(0)
        command_run.send(r, f"CLOCK,{time.time_ns() // 1000},{int(offset.total_seconds()) // 60}")
        prompt("Make sure Home shows, then follow each step.")

        step(r, 1, "Tap Home once.")
        wait_for(r, [word_is("TOUCH"), word_is("SCREEN_VIEW", screen="medication"), word_is("TONE_PLAY")],
                 STEP_WAIT_S)
        read_for(r, SETTLE_S)

        step(r, 2, "Wait 2 seconds, then tap the upper half of Medication once.")
        wait_for(r, [word_is("TOUCH")], STEP_WAIT_S)
        read_for(r, SETTLE_S)

        step(r, 3, 'Tap "Took it" once.')
        needs = [word_is("TOUCH"), word_is("SCREEN_VIEW", screen="logged"), word_is("SCREEN_VIEW", screen="home")]
        wait_for(r, needs, STEP_WAIT_S)
        read_for(r, SETTLE_S)

        step(r, 4, "Tap Home twice quickly.")
        wait_for(r, [word_is("TOUCH"), word_is("TOUCH")], STEP_WAIT_S)
        read_for(r, SETTLE_S)

        step(r, 5, 'Tap "Took it" twice quickly.')
        wait_for(r, [word_is("TOUCH"), word_is("TOUCH"), word_is("SCREEN_VIEW", screen="home")], STEP_WAIT_S)
        read_for(r, SETTLE_S)

        now = datetime.now().astimezone()
        minute = dose_minute(now)
        step(r, 6, "Wait for the three dose tones. Then press BOOT once to open Medication and tap \"Took it\".")
        command_run.send(r, f"SCHEDULE,{DOSE_NAME},{minute}")
        wait_for(r, [is_due_face, word_is("TONE_PLAY", tones="3")], LEAD_S + 60 + STEP_WAIT_S)
        wait_for(r, [word_is("BUTTON"), letter_is("D")], STEP_WAIT_S)
        # The Logged view ends before step 7, which starts on Home.
        wait_for(r, [word_is("SCREEN_VIEW", screen="home")], STEP_WAIT_S)
        read_for(r, SETTLE_S)

        step(r, 7, "Start on Home and press BOOT four times, one second apart.")
        wait_for(r, [word_is("BUTTON")] * 4, STEP_WAIT_S)
        read_for(r, SETTLE_S)

        step(r, 8, "Press BOOT twice to open Session, then do not touch the watch for 5 minutes.")
        wait_for(r, [word_is("BUTTON")] * 2, STEP_WAIT_S)
        wait_for(r, [word_is("SCREEN_VIEW", screen="home")], IDLE_WAIT_S)
        read_for(r, SETTLE_S)

        step(r, 9, "Tap Home once.")
        command_run.send(r, "TONE,0")
        wait_for(r, [word_is("TOUCH")], STEP_WAIT_S)
        read_for(r, NO_TONE_S + SETTLE_S)
        command_run.send(r, f"TONE,{boot_settings.get('tone', '1')}")

        for text in command_run.restore_commands(boot_settings):
            command_run.send(r, text)
        read_for(r, SETTLE_S)
        r.ser.close()
        prompt("Done. The settings are back.")


# ---------------------------------------------------------------- judge


@dataclass
class TapLog:
    """The lines of a tap log and the lines of each step."""

    lines: list[Line]
    steps: dict[int, list[Line]]


def parse_log(entries: list[Entry]) -> TapLog:
    """Split the log at its "> STEP n" lines."""
    lines = [Line(i, e.seconds, e.text, e.text.split(" ", 1)[0], fields_of(e.text)) for i, e in enumerate(entries)]
    steps: dict[int, list[Line]] = {}
    current: int | None = None
    for line in lines:
        match = re.fullmatch(rf"> {STEP} (\d+)", line.text)
        if match:
            current = int(match.group(1))
            steps[current] = []
        elif current is not None:
            steps[current].append(line)
    return TapLog(lines, steps)


def at_us(line: Line) -> int:
    """Give the at_us field of a diagnostic line."""
    return int(line.fields.get("at_us", "0"))


def result(name: str, problems: list[str], detail: str = "") -> Check:
    """Make a check from a list of problems."""
    text = detail or f"{len(problems)} problems"
    return Check(name, not problems, text + (f", first: {problems[0]}" if problems else ""))


def of(lines: list[Line], word: str, **want: str) -> list[Line]:
    """Give the diagnostic lines with a first word and some field values."""
    return [line for line in lines if line.word == word and all(line.fields.get(k) == v for k, v in want.items())]


def records(lines: list[Line], letter: str) -> list[Line]:
    """Give the record lines of one letter."""
    return [line for line in lines if kind_of(line.text) == letter]


def after(lines: list[Line], line: Line) -> list[Line]:
    """Give the lines after one line."""
    return [later for later in lines if later.index > line.index]


def check_step1(log: TapLog) -> Check:
    """Check a tap on Home that opens Medication with the tap tone."""
    lines = log.steps.get(1, [])
    touches = of(lines, "TOUCH", target="home", accepted="1")
    if not touches:
        return result("step 1 tap on Home", ["no TOUCH line with target=home and accepted=1"])
    problems = []
    if not of(after(lines, touches[0]), "SCREEN_VIEW", screen="medication"):
        problems.append("no SCREEN_VIEW with screen=medication")
    if not of(after(lines, touches[0]), "TONE_PLAY", kind="tap"):
        problems.append("no TONE_PLAY with kind=tap")
    return result("step 1 tap on Home", problems)


def check_step2(log: TapLog) -> Check:
    """Check that a tap on the upper half of Medication is ignored."""
    lines = log.steps.get(2, [])
    touches = of(lines, "TOUCH")
    if not touches:
        return result("step 2 upper half", ["no TOUCH line"])
    problems = []
    if touches[0].fields.get("accepted") != "0":
        problems.append(f"the tap gives {touches[0].text}")
    if of(lines, "DOSE") or records(lines, "D"):
        problems.append("a DOSE or D line came")
    moved = [line for line in of(lines, "SCREEN_VIEW") if line.fields.get("screen") != "medication"]
    moved += of(lines, "BUTTON")
    if moved:
        problems.append(f"the screen changed: {moved[0].text}")
    return result("step 2 upper half", problems)


def check_step3(log: TapLog) -> Check:
    """Check one "Took it" tap, its dose, and the Logged view for 3 seconds."""
    lines = log.steps.get(3, [])
    touches = of(lines, "TOUCH", target="took_it", accepted="1")
    if not touches:
        return result("step 3 took it", ["no TOUCH line with target=took_it and accepted=1"])
    tap = touches[0]
    problems = []
    for name, found in (("DOSE", of(after(lines, tap), "DOSE")), ("D", records(after(lines, tap), "D"))):
        if not found or found[0].seconds - tap.seconds > WITHIN_S:
            problems.append(f"no {name} line within {WITHIN_S} s of the tap")
    logged = of(after(lines, tap), "SCREEN_VIEW", screen="logged")
    if not logged:
        problems.append("no SCREEN_VIEW with screen=logged")
        return result("step 3 took it", problems)
    home = of(after(lines, logged[0]), "SCREEN_VIEW", screen="home")
    span = at_us(home[0]) - at_us(logged[0]) if home else -1
    if not LOGGED_MIN_US <= span <= LOGGED_MAX_US:
        problems.append(f"Home came {span} us after Logged")
    return result("step 3 took it", problems, f"Logged lasted {span / 1e6:.3f} s")


def check_step4(log: TapLog) -> Check:
    """Check that a quick second tap after Home opens Medication is ignored."""
    lines = log.steps.get(4, [])
    touches = of(lines, "TOUCH")
    problems = []
    if not of(lines, "SCREEN_VIEW", screen="medication"):
        problems.append("no SCREEN_VIEW with screen=medication")
    if len(touches) < 2:
        problems.append(f"{len(touches)} TOUCH lines")
    else:
        if touches[1].seconds - touches[0].seconds > WITHIN_S:
            problems.append("the second TOUCH came more than 1 s after the first")
        if touches[1].fields.get("accepted") != "0":
            problems.append(f"the second tap gives {touches[1].text}")
    if of(lines, "DOSE"):
        problems.append("a DOSE line came")
    return result("step 4 double tap on Home", problems)


def check_step5(log: TapLog) -> Check:
    """Check that two quick "Took it" taps log one dose."""
    lines = log.steps.get(5, [])
    touches = of(lines, "TOUCH")
    doses = of(lines, "DOSE")
    d_lines = records(lines, "D")
    problems = []
    if len(doses) != 1 or len(d_lines) != 1:
        problems.append(f"{len(doses)} DOSE lines and {len(d_lines)} D lines")
    if len(touches) < 2 or touches[1].fields.get("accepted") != "0":
        problems.append("no second TOUCH line with accepted=0")
    return result("step 5 double tap on Took it", problems)


def dose_local(minute: int, d_local_us: int) -> int:
    """Give the local time of the dose minute nearest to the D line's local time."""
    day = d_local_us // DAY_US
    candidates = [(day + k) * DAY_US + minute * MINUTE_US for k in (-1, 0, 1)]
    return min(candidates, key=lambda t: abs(t - d_local_us))


def check_step6(log: TapLog) -> Check:
    """Check the due dose, the BOOT press, and the "Took it" tap that ends it."""
    lines = log.steps.get(6, [])
    problems = []
    schedule = next((line for line in lines if line.text.startswith(f"> SCHEDULE,{DOSE_NAME},")), None)
    clock = next((line for line in log.lines if line.word == "CLOCK" and "offset_us" in line.fields), None)
    if schedule is None or clock is None:
        return result("step 6 due dose", ["no SCHEDULE command or no CLOCK line"])
    minute = int(schedule.text.rsplit(",", 1)[1])
    due = [line for line in records(lines, "F") if record_fields(line.text)[1] == "4"]
    if not due:
        problems.append("no F line with state 4")
    if not of(lines, "TONE_PLAY", tones="3"):
        problems.append("no TONE_PLAY with tones=3")
    if not of(lines, "BUTTON", screen="medication"):
        problems.append("no BUTTON line with screen=medication")
    d_lines = records(lines, "D")
    if not d_lines or not due:
        problems.append("no D line after the due F line")
        return result("step 6 due dose", problems)
    d = d_lines[0]
    time_us, answered = record_fields(d.text)
    offset_us = int(clock.fields["offset_us"])
    want = dose_local(minute, int(time_us) + offset_us)
    if answered != str(want):
        problems.append(f"the D line answers {answered}, want {want}")
    back = next((line for line in records(after(lines, d), "F")), None)
    if back is None or record_fields(back.text)[1] == "4":
        problems.append("no F line back to the detector state after the D line")
    elif not 0 <= int(record_fields(back.text)[0]) - int(time_us) <= FACE_BACK_US:
        problems.append(f"the F line came {int(record_fields(back.text)[0]) - int(time_us)} us after the tap")
    if not of(after(lines, d), "SCREEN_VIEW", due="0"):
        problems.append("no SCREEN_VIEW with due=0 after the D line")
    return result("step 6 due dose", problems)


def check_step7(log: TapLog) -> Check:
    """Check that four BOOT presses cycle through the screens back to Home."""
    buttons = [line.fields.get("screen", "") for line in of(log.steps.get(7, []), "BUTTON")]
    want = ["medication", "session", "status", "home"]
    return Check("step 7 BOOT cycle", buttons[:4] == want and len(buttons) == 4, f"BUTTON screens {buttons}")


def check_step8(log: TapLog) -> Check:
    """Check that Session goes back to Home 5 minutes after the last BOOT press."""
    lines = log.steps.get(8, [])
    buttons = of(lines, "BUTTON")
    if not buttons:
        return result("step 8 five minute return", ["no BUTTON line"])
    home = of(after(lines, buttons[-1]), "SCREEN_VIEW", screen="home")
    span = at_us(home[0]) - at_us(buttons[-1]) if home else -1
    problems = [] if IDLE_MIN_US <= span <= IDLE_MAX_US else [f"Home came {span} us after the last BUTTON line"]
    return result("step 8 five minute return", problems, f"Home came {span / 1e6:.3f} s after the last press")


def check_step9(log: TapLog) -> Check:
    """Check that a tap with the tone off plays no tone."""
    lines = log.steps.get(9, [])
    problems = []
    if not any(line.text == "> TONE,0" for line in lines):
        problems.append("no TONE,0 command")
    touches = of(lines, "TOUCH", accepted="1")
    if not touches:
        problems.append("no TOUCH line with accepted=1")
    else:
        tones = [line for line in of(after(lines, touches[0]), "TONE_PLAY")
                 if line.seconds - touches[0].seconds <= NO_TONE_S]
        if tones:
            problems.append(f"a TONE_PLAY came: {tones[0].text}")
    return result("step 9 tone off", problems)


def check_steps(log: TapLog) -> Check:
    """Check that the log holds every step."""
    missing = [n for n in range(1, STEP_COUNT + 1) if n not in log.steps]
    return result("every step ran", [f"step {n} is missing" for n in missing])


def check_format(log: TapLog) -> Check:
    """Check one B line and that every record line follows its pattern.

    The port opens with no reset. The watch repeats its B line after lines were
    dropped while nobody read the port, so the log holds one B line."""
    boots = records(log.lines, "B")
    bad = [line.text for line in log.lines if kind_of(line.text) and not record_run.is_record(line.text)]
    problems = [f"{len(boots)} B lines"] if len(boots) != 1 else []
    problems += [f"bad record line {text!r}" for text in bad]
    if boots and record_run.boot_problems(boots[0].text):
        problems += record_run.boot_problems(boots[0].text)
    return result("B line and record format", problems, f"{len(boots)} B lines, {len(bad)} bad record lines")


def replay_bad(texts: list[str]) -> int | None:
    """Run replay on the log's text and give its count of bad lines, or None."""
    run = subprocess.run([str(REPLAY), "--recording", "-"], input="\n".join(texts) + "\n", capture_output=True,
                         text=True, check=False)
    match = re.search(r"^replay: lines=\d+ bad=(\d+)", run.stderr, re.MULTILINE)
    return int(match.group(1)) if match else None


def check_replay(log: TapLog) -> Check:
    """Check that replay finds no bad line."""
    bad = replay_bad([line.text for line in log.lines])
    return Check("replay gives bad=0", bad == 0, f"bad={bad}")


def check_settings(log: TapLog) -> Check:
    """Check that the last SETTINGS line gives the tone, times, and name of the first one."""
    settings = of(log.lines, "SETTINGS")
    if not settings:
        return result("settings put back", ["no SETTINGS line"])
    keys = ("tone", "times", "name")
    first = {k: settings[0].fields.get(k, "") for k in keys}
    last = {k: settings[-1].fields.get(k, "") for k in keys}
    return Check("settings put back", first == last, f"first {first}, last {last}")


def judge(log: TapLog) -> list[Check]:
    """Give the result of every pass check."""
    return [
        check_steps(log),
        check_step1(log),
        check_step2(log),
        check_step3(log),
        check_step4(log),
        check_step5(log),
        check_step6(log),
        check_step7(log),
        check_step8(log),
        check_step9(log),
        check_format(log),
        check_replay(log),
        check_settings(log),
    ]


def write_report(path: Path, checks: list[Check]) -> None:
    """Write the report with the checks."""
    lines = ["# Tap run", "", "## Pass checks", ""]
    lines += [f"- {'PASS' if c.passed else 'FAIL'}: {c.name}. {c.detail}" for c in checks]
    path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run or judge the tap run and give the exit code."""
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
    write_report(args.report, checks)
    for check in checks:
        LOG.info("%s: %s. %s", "PASS" if check.passed else "FAIL", check.name, check.detail)
    return 0 if all(check.passed for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
