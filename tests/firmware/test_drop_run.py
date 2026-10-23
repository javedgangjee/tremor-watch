"""Tests for tests/firmware/drop_run.py.

Each case writes a made-up gzip log with the "> CLOSE" and "> OPEN" lines and
judges it with --log-only, so no watch is needed. In the made-up log the port
closes at 80 seconds, the lines of the next second still arrive after the port
opens, and the lines of the 60 seconds after that are lost. They run in the
reference venv with this command.

    reference/.venv/bin/python -m pytest tests/firmware -q
"""
from __future__ import annotations

import gzip
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
DROP_RUN = HERE / "drop_run.py"

T0 = 233_166
BURST_US = 96_200
RATE_UHZ = 114_354_601
CLOSE_US = 80_000_000
OPEN_US = 81_000_000
BACK_US = 141_000_000
END_US = 200_000_000
FIRST_ANSWER = T0 + 10_000_000


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


def watch_lines(port_drops: int) -> list[tuple[int, str]]:
    """Give every line the watch writes in 200 seconds, with its watch time."""
    restarts = 1 if port_drops > 0 else 0
    lines = [
        (0, f"B,305419896,11,9,{table_hash()}"),
        (1, "START uptime_us=61369"),
        (2, "TASK name=usb core=0 priority=3"),
        (T0, f"STRETCH number=0 first=0 t0_us={T0} kind=start reason=start prev_span_us=0 prev_readings=0 "
             "prev_rate_uhz=0 error_us=none"),
        (T0, f"S,0,0,{T0},0,1024"),
        (T0 + 10_000_000, f"S,0,0,{T0},{RATE_UHZ},1024"),
        (T0 + 10_000_001, f"RATE number=0 rate_uhz={RATE_UHZ}"),
    ]
    n = 0
    while T0 + n * BURST_US < END_US:
        stamp = T0 + n * BURST_US
        lines.append((stamp + 1, f"T,{11 * n},11,{stamp}"))
        lines += [(stamp + 2 + i, f"R,{11 * n + i},3,-5,2,-146,-24,-3773") for i in range(11)]
        n += 1
    w = 0
    while FIRST_ANSWER + w * 1_000_000 < END_US:
        at = FIRST_ANSWER + w * 1_000_000
        code = 3 if w == 0 else 1
        lines += [
            (at, f"ANSWER stretch=0 window={w} code={code} prob=0.0001 below=0.5 peak=7.5 time_us={at - 100_000} "
                 f"at_us={at} run_us=6870 delay_us=12400 counted=0 face={3 if w < 2 else 1}"),
            (at, f"W,0,{w},{code},0.0001,0.5,7.5"),
        ]
        w += 1
    for minute in range(1, END_US // 60_000_000 + 1):
        mark = minute * 60_000_000
        drops = port_drops if mark > OPEN_US else 0
        lines += [
            (mark + 10, f"SENSOR_MINUTE minute={minute} readings={6860 * minute} msg_drops=0 record_drops=0"),
            (mark + 20, f"PIPELINE_MINUTE minute={minute} answer_drops=0 faults=0 stack_free=2528"),
            (mark + 30, f"STATE_MINUTE minute={minute} screen_drops=0 stack_free=2252"),
            (mark + 50, f"USB_MINUTE minute={minute} line_drops=0 port_drops={drops} "
                        f"restarts={restarts if mark > OPEN_US else 0} bytes=250000 commands=0 bad_commands=0 "
                        "stack_free=2668"),
        ]
    if port_drops > 0:
        lines += [(BACK_US - 2, f"B,305419896,11,9,{table_hash()}"), (BACK_US - 1, f"S,0,0,{T0},{RATE_UHZ},1024")]
    return sorted(lines, key=lambda e: e[0])


def make_log(port_drops: int) -> list[str]:
    """Give a drop log. The lines from OPEN_US to BACK_US never arrive."""
    lines = ["ESP-ROM:esp32s3-20210327"]
    for at, text in watch_lines(port_drops):
        if at < CLOSE_US:
            lines.append(text)
    lines.append("> CLOSE")
    lines.append("> OPEN")
    for at, text in watch_lines(port_drops):
        if CLOSE_US <= at < OPEN_US or at >= BACK_US - 2:
            lines.append(text)
    return lines


def judge(lines: list[str], tmp_path: Path) -> tuple[int, str]:
    """Write the lines as a saved gzip log, judge it, and give the exit code and the report."""
    log = tmp_path / "log.txt.gz"
    report = tmp_path / "report.md"
    with gzip.open(log, "wt") as out:
        out.write("".join(f"{i * 0.001:.3f}\t{line}\n" for i, line in enumerate(lines)))
    code = load("drop_run", DROP_RUN).main(["--log-only", "--log", str(log), "--report", str(report)])
    return code, report.read_text()


def test_drops_with_repeated_lines(tmp_path: Path) -> None:
    """Case 8 judges a log where the watch dropped 3 lines and repeated the B and S lines."""
    code, report = judge(make_log(3), tmp_path)
    assert code == 0, report
    assert "The watch dropped 3 lines" in report


def test_lines_lost_on_the_laptop(tmp_path: Path) -> None:
    """Case 9 judges a log where the watch dropped nothing and the laptop lost lines."""
    code, report = judge(make_log(0), tmp_path)
    assert code == 0, report
    assert "The watch dropped no line" in report
    assert "The lines were lost on the laptop's side" in report


def test_changed_logs_fail(tmp_path: Path) -> None:
    """Case 10 checks five changed copies of case 8's log."""
    clean = make_log(3)
    opened = clean.index("> OPEN")
    boot_at_gap = next(i for i, line in enumerate(clean) if i > opened and line.startswith("B,"))
    copies: list[list[str]] = []

    lines = list(clean)
    lines.insert(boot_at_gap + 1, "START uptime_us=61369")
    copies.append(lines)

    lines = list(clean)
    del lines[boot_at_gap]
    copies.append(lines)

    lines = list(clean)
    last = max(i for i, line in enumerate(lines) if line.startswith("USB_MINUTE "))
    lines[last] = lines[last].replace("line_drops=0", "line_drops=2")
    copies.append(lines)

    lines = list(clean)
    i = next(i for i, line in enumerate(lines) if i > boot_at_gap and line.startswith("ANSWER "))
    window = int(re.search(r"window=(\d+)", lines[i]).group(1))
    lines[i] = lines[i].replace(f"window={window} ", f"window={window - 30} ")
    copies.append(lines)

    lines = list(clean)
    lines.insert(opened + 1, "R,1234,5")
    copies.append(lines)

    assert len(copies) == 5
    for n, lines in enumerate(copies):
        assert lines != clean, n
        assert judge(lines, tmp_path)[0] == 1, n
