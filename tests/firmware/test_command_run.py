"""Tests for tests/firmware/command_run.py.

Each case writes a made-up gzip log of every step of command_run.py and judges it with
--log-only, so no watch is needed. The scheduled minute is 600, the offset is
60 minutes, and the CLOCK command's UTC time is 08:57:00 on 23 October 2026.
They run in the reference venv with this command.

    reference/.venv/bin/python -m pytest tests/firmware -q
"""
from __future__ import annotations

import gzip
import importlib.util
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
COMMAND_RUN = HERE / "command_run.py"

MINUTE = 600
OFFSET_MIN = 60
UTC_US = int(datetime(2026, 10, 23, 8, 57, tzinfo=timezone.utc).timestamp()) * 1_000_000
CLOCK_AT = 70_000_000
# The watch time of the dose time T, 3 minutes after the clock command.
T_WATCH = CLOCK_AT + 180_000_000
TICK = 400_000
DUE_US = 900_000_000
SESSION_AT = T_WATCH + DUE_US + 15_000_000
FIRST_ANSWER = 10_300_000
BOOT_IDS = (305419896, 2271560481)
OFFSET_US = UTC_US + OFFSET_MIN * 60_000_000 - CLOCK_AT


def load(name: str, path: Path) -> ModuleType:
    """Import a module from its path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The dataclasses in the module look it up by name.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def table_hash() -> str:
    """Read DET_MODEL_SHA256 from core/detector_tables.h."""
    text = (HERE.parents[1] / "core" / "detector_tables.h").read_text()
    match = re.search(r'^#define DET_MODEL_SHA256 "([0-9a-f]{64})"', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


def boot_start(boot_id: int, settings: str) -> list[tuple[int, str]]:
    """Give the first lines of a boot from the ROM text on, with a few T and R lines."""
    version = load("record_run", HERE / "record_run.py").FIRMWARE_VERSION
    lines = [
        (0, "ESP-ROM:esp32s3-20210327"),
        (0, "rst:0x15 (USB_UART_CHIP_RESET),boot:0x2b (SPI_FAST_FLASH_BOOT)"),
        (600_000, f"B,{boot_id},11,{version},{table_hash()}"),
        (600_001, "START uptime_us=61335"),
        (600_002, "TASK name=usb core=0 priority=3"),
        (600_003, "TASK name=state core=0 priority=6"),
        (600_004, settings),
        (800_000, "STRETCH number=0 first=0 t0_us=233166 kind=start reason=start prev_span_us=0 "
                  "prev_readings=0 prev_rate_uhz=0 error_us=none"),
        (800_001, "S,0,0,233166,0,1024"),
    ]
    for n in range(2):
        stamp = 233_166 + 96_200 * n
        lines.append((stamp + 600_000, f"T,{11 * n},11,{stamp}"))
        lines += [(stamp + 600_001 + i, f"R,{11 * n + i},3,-5,2,-146,-24,-3773") for i in range(11)]
    return lines


def answer(n: int, at: int, face: int, code: int = 1) -> str:
    """Give an ANSWER line."""
    return (
        f"ANSWER stretch=0 window={n} code={code} prob=0.0001 below=0.5 peak=7.5 time_us={at - 100_000} "
        f"at_us={at} run_us=6870 delay_us=12400 counted=0 face={face}"
    )


def w_line(n: int, code: int = 1) -> str:
    """Give the W line of an answer."""
    return f"W,0,{n},{code},0.0001,0.5,7.5"


def face_lines(at: int, state: int) -> list[tuple[int, str]]:
    """Give a FACE line and its F line."""
    return [(at, f"FACE at_us={at} state={state}"), (at, f"F,{at},{state}")]


def boot1() -> list[tuple[int, str]]:
    """Give boot 1 up to the second reset, with the watch's answers to each command."""
    lines = boot_start(BOOT_IDS[0], "SETTINGS source=boot store=empty tone=1 times=none name=")
    for n in range(3):
        at = FIRST_ANSWER + n * 1_000_000
        lines += [(at, answer(n, at, 3 if n < 2 else 1, 3 if n == 0 else 1)), (at, w_line(n, 3 if n == 0 else 1))]
    lines += face_lines(FIRST_ANSWER + 2_000_001, 1)
    at = 13_000_000
    command_run = load("command_run", COMMAND_RUN)
    for text, reply in command_run.BAD_COMMANDS:
        lines += [(at, f"> {text}"), (at + 1000, reply)]
        at += 100_000
    lines += [
        (at, "> TONE,0"),
        (at + 1000, "SETTINGS source=command store=ok tone=0 times=none name="),
        (at + 1001, "A,4,0"),
        (at + 100_000, f"> SCHEDULE,TestDose,{MINUTE}"),
        (at + 101_000, f"SETTINGS source=command store=ok tone=0 times={MINUTE} name=TestDose"),
        (at + 101_001, "A,2,0"),
    ]
    return lines


def face_at(at: int, n: int, n_since: int) -> int:
    """Give the shown face after boot 2's answer at a watch time. Window 0 is
    warming up, so the face first changes at the third answer of the boot and
    at the second answer of a new session."""
    if T_WATCH + TICK <= at < T_WATCH + TICK + DUE_US:
        return 4
    if at > SESSION_AT:
        return 3 if n_since < 1 else 1
    return 3 if n < 2 else 1


def boot2() -> list[tuple[int, str]]:
    """Give boot 2 from its ROM text to the last command."""
    lines = boot_start(BOOT_IDS[1], f"SETTINGS source=boot store=ok tone=0 times={MINUTE} name=TestDose")
    clock_local = CLOCK_AT + OFFSET_US
    lines += [
        (CLOCK_AT, f"> CLOCK,{UTC_US},{OFFSET_MIN}"),
        (CLOCK_AT + 1000, f"CLOCK at_us={CLOCK_AT} offset_us={OFFSET_US} local_us={clock_local}"),
        (CLOCK_AT + 1001, "A,1,0"),
        (T_WATCH + TICK, "TONE enabled=0"),
    ]
    lines += face_lines(T_WATCH + TICK + 1, 4)
    lines += face_lines(T_WATCH + TICK + DUE_US + 1, 1)
    lines += [
        (SESSION_AT, "> SESSION"),
        (SESSION_AT + 1000, f"SESSION at_us={SESSION_AT + 1000} changed=1"),
    ]
    lines += face_lines(SESSION_AT + 1001, 3)
    lines.append((SESSION_AT + 1002, "A,3,0"))
    end = SESSION_AT + 70_000_000
    n_since = 0
    n = 0
    at = FIRST_ANSWER
    while at < end:
        code = 3 if n == 0 else 1
        face = face_at(at, n, n_since)
        lines += [(at, answer(n, at, face, code)), (at, w_line(n, code))]
        if at > SESSION_AT:
            n_since += 1
            if n_since == 2:
                lines += face_lines(at + 1, 1)
        elif n == 2:
            lines += face_lines(at + 1, 1)
        n += 1
        at += 1_000_000
    for minute in range(1, end // 60_000_000 + 1):
        mark = minute * 60_000_000 + 30_000
        count = sum(1 for k in range(n) if FIRST_ANSWER + k * 1_000_000 < mark)
        if mark > SESSION_AT:
            count = sum(1 for k in range(n) if SESSION_AT < FIRST_ANSWER + k * 1_000_000 < mark)
        due = int(T_WATCH + TICK <= mark < T_WATCH + TICK + DUE_US)
        lines.append(
            (
                mark,
                f"STATE_MINUTE minute={minute} answers={count} face=1 screen_drops=0 stack_free=2252 "
                f"clock={int(mark > CLOCK_AT)} schedule=1 due={due} doses=0 tone=0",
            )
        )
        lines.append((mark + 1, f"USB_MINUTE minute={minute} line_drops=0 port_drops=0 restarts=0 stack_free=2668"))
    after = end + 1_000_000
    lines += [
        (after, "> TONE,1"),
        (after + 1000, f"SETTINGS source=command store=ok tone=1 times={MINUTE} name=TestDose"),
        (after + 1001, "A,4,0"),
        (after + 100_000, "> SCHEDULE"),
        (after + 101_000, "SETTINGS source=command store=ok tone=1 times=none name="),
        (after + 101_001, "A,2,0"),
        (after + 200_000, "> TONE,1"),
        (after + 201_000, "SETTINGS source=command store=ok tone=1 times=none name="),
        (after + 201_001, "A,4,0"),
    ]
    return lines


def make_log() -> list[str]:
    """Give the clean log of every step in order."""
    out = ["> RESET"]
    out += [text for _, text in sorted(boot1(), key=lambda e: e[0])]
    out.append("> RESET")
    out += [text for _, text in sorted(boot2(), key=lambda e: e[0])]
    return out


def judge(lines: list[str], tmp_path: Path) -> tuple[int, str]:
    """Write the lines as a saved gzip log, judge it, and give the exit code and the report."""
    log = tmp_path / "log.txt.gz"
    report = tmp_path / "report.md"
    with gzip.open(log, "wt") as out:
        out.write("".join(f"{i * 0.001:.3f}\t{line}\n" for i, line in enumerate(lines)))
    code = load("command_run", COMMAND_RUN).main(["--log-only", "--log", str(log), "--report", str(report)])
    return code, report.read_text()


def find(lines: list[str], start: str, after: int = 0) -> int:
    """Give the place of the first line that starts with some text after a place."""
    return next(i for i, line in enumerate(lines) if i >= after and line.startswith(start))


def test_clean_log_passes(tmp_path: Path) -> None:
    """Judge the clean log."""
    code, report = judge(make_log(), tmp_path)
    assert code == 0, report
    assert "FAIL" not in report


def test_changed_logs_fail(tmp_path: Path) -> None:
    """Check eleven changed copies of the clean log."""
    clean = make_log()
    boot2_at = find(clean, "> RESET", 1)
    due_f = f"F,{T_WATCH + TICK + 1},4"
    end_f = f"F,{T_WATCH + TICK + DUE_US + 1},1"
    copies: list[list[str]] = []

    lines = list(clean)
    lines[find(lines, "> TONE,2") + 1] = "A,4,0"
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "SETTINGS source=boot", boot2_at)
    lines[i] = lines[i].replace("tone=0", "tone=1")
    copies.append(lines)

    lines = list(clean)
    lines[lines.index(due_f)] = f"F,{T_WATCH + 2_000_000},4"
    copies.append(lines)

    lines = list(clean)
    lines.remove(due_f)
    copies.append(lines)

    lines = list(clean)
    lines[lines.index(end_f)] = f"F,{T_WATCH + 899_000_000},1"
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "ANSWER", lines.index(due_f))
    lines[i] = lines[i].replace("face=4", "face=1")
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "B,", boot2_at)
    lines[i] = lines[i].replace(str(BOOT_IDS[1]), str(BOOT_IDS[0]))
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "CLOCK at_us=")
    lines[i] = lines[i].replace(f"local_us={CLOCK_AT + OFFSET_US}", f"local_us={CLOCK_AT + OFFSET_US + 3_000_000}")
    copies.append(lines)

    lines = list(clean)
    lines.insert(lines.index("> SESSION"), "TONE enabled=0")
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "STATE_MINUTE", find(lines, "SESSION at_us="))
    lines[i] = re.sub(r"answers=\d+", "answers=500", lines[i])
    copies.append(lines)

    lines = list(clean)
    lines.insert(find(lines, "> CLOCK,", boot2_at), "F,65000000,4")
    copies.append(lines)

    assert len(copies) == 11
    for n, lines in enumerate(copies):
        assert lines != clean, n
        assert judge(lines, tmp_path)[0] == 1, n


def test_restore_commands() -> None:
    """Check the commands that put back the settings of a SETTINGS line."""
    command_run = load("command_run", COMMAND_RUN)
    fields = load("table_run", HERE / "table_run.py").fields_of
    empty = fields("SETTINGS source=boot store=empty tone=1 times=none name=")
    assert command_run.restore_commands(empty) == ["SCHEDULE", "TONE,1"]
    stored = fields("SETTINGS source=boot store=ok tone=0 times=480,1200 name=Levodopa")
    assert command_run.restore_commands(stored) == ["SCHEDULE,Levodopa,480,1200", "TONE,0"]
