"""Tests for tests/firmware/record_run.py.

Each case writes a made-up gzip log and judges it with --log-only and
--minutes 3, so no watch is needed. The clean log is the clean log of
test_pipeline_run.make_log(False) with the record lines added. They run in the
reference venv with this command.

    reference/.venv/bin/python -m pytest tests/firmware -q
"""
from __future__ import annotations

import ast
import gzip
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
RECORD_RUN = HERE / "record_run.py"
PIPELINE_LOG = HERE / "pipeline_log.txt"
SCRIPTS = (RECORD_RUN, HERE / "command_run.py", HERE / "drop_run.py")
TEST_FILES = (HERE / "test_record_run.py", HERE / "test_command_run.py", HERE / "test_drop_run.py")

MINUTES = 3
BOOT_ID = 305419896
RESET_CAUSE = 11
RATE_UHZ = 114330200
BURST = 11
BURST_US = 96_200
USB_TAIL = " port_drops=0 restarts=0 bytes=900000 commands=0 bad_commands=0 stack_free=2000"


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


def boot_line(boot_id: int = BOOT_ID) -> str:
    """Give a good B line."""
    return f"B,{boot_id},{RESET_CAUSE},9,{table_hash()}"


def value(text: str, key: str) -> str:
    """Give one key=value field of a diagnostic line."""
    match = re.search(rf"\b{key}=(\S+)", text)
    assert match is not None, text
    return match.group(1)


def time_of(text: str, before: int) -> int:
    """Give the watch time of a diagnostic line, or the time of the line before it."""
    word = text.split(" ", 1)[0]
    if word in ("ANSWER", "FACE"):
        return int(value(text, "at_us"))
    if word == "STRETCH":
        return int(value(text, "t0_us"))
    if word.endswith("_MINUTE"):
        return int(value(text, "minute")) * 60_000_000
    return before


def burst_lines(t0: int, readings: int) -> list[tuple[int, list[str]]]:
    """Give the T and R lines of 11 readings each from reading 0 until they cover the readings."""
    out = []
    first = 0
    while first < readings:
        stamp = t0 + (first // BURST) * BURST_US
        lines = [f"T,{first},{BURST},{stamp}"]
        lines += [f"R,{first + i},{i - 5},{2 * i},-{i},-146,-24,-3773" for i in range(BURST)]
        out.append((stamp, lines))
        first += BURST
    return out


def clean_log() -> list[str]:
    """Give the clean log of 3 minutes with every record line."""
    base = load("test_pipeline_run", HERE / "test_pipeline_run.py").make_log(False)
    t0 = int(value(next(t for t in base if t.startswith("STRETCH ")), "t0_us"))
    readings = int(value([t for t in base if t.startswith("SENSOR_MINUTE ")][-1], "readings"))
    timed: list[tuple[int, int, str]] = []
    now = 0
    for text in base:
        now = time_of(text, now)
        added = [text]
        if text.startswith("START "):
            added = [boot_line(), text]
        elif text.startswith("SENSOR_MINUTE "):
            added = [text + " record_drops=0"]
        elif text.startswith("USB_MINUTE "):
            added = [text + USB_TAIL]
        elif text.startswith("STRETCH "):
            added.append(f"S,0,0,{t0},0,1024")
        elif text.startswith("RATE "):
            added.append(f"S,0,0,{t0},{RATE_UHZ},1024")
        elif text.startswith("ANSWER "):
            f = {k: value(text, k) for k in ("stretch", "window", "code", "prob", "below", "peak")}
            added.append(f"W,{f['stretch']},{f['window']},{f['code']},{f['prob']},{f['below']},{f['peak']}")
        elif text.startswith("FACE "):
            added.append(f"F,{value(text, 'at_us')},{value(text, 'state')}")
        for line in added:
            timed.append((now, 0, line))
    for stamp, lines in burst_lines(t0, readings):
        for line in lines:
            timed.append((stamp, 1, line))
    # The S line of the stretch must come before its first T line, so record
    # lines at the same time go after the diagnostic lines.
    timed.sort(key=lambda e: (e[0], e[1]))
    return [text for _, _, text in timed]


def judge(lines: list[str], tmp_path: Path) -> tuple[int, str]:
    """Write the lines as a saved gzip log, judge it, and give the exit code and the report."""
    log = tmp_path / "log.txt.gz"
    report = tmp_path / "report.md"
    with gzip.open(log, "wt") as out:
        out.write("".join(f"{i * 0.001:.3f}\t{line}\n" for i, line in enumerate(lines)))
    code = load("record_run", RECORD_RUN).main(
        ["--log-only", "--minutes", str(MINUTES), "--log", str(log), "--report", str(report)]
    )
    return code, report.read_text()


def find(lines: list[str], start: str, last: bool = False) -> int:
    """Give the place of the first or the last line that starts with some text."""
    places = [i for i, line in enumerate(lines) if line.startswith(start)]
    return places[-1] if last else places[0]


def test_clean_log_passes(tmp_path: Path) -> None:
    """Case 1 judges the clean log and checks the report's measurements."""
    code, report = judge(clean_log(), tmp_path)
    assert code == 0, report
    assert "FAIL" not in report
    assert "bytes a second" in report
    for kind in ("PIPELINE_MINUTE", "STATE_MINUTE", "USB_MINUTE"):
        assert f"- {kind} gives the free stack in bytes at each minute as" in report


def test_changed_logs_fail(tmp_path: Path) -> None:
    """Case 2 checks eleven changed copies of the clean log."""
    clean = clean_log()
    copies: list[list[str]] = []

    lines = list(clean)
    del lines[find(lines, "R,500,")]
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "T,550,")
    lines[i] = lines[i].replace("T,550,11,", "T,550,10,")
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "W,0,20,")
    lines[i] = lines[i].replace(",0.0001,", ",0.00010,")
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "F,")
    lines[i] = lines[i][: lines[i].rfind(",")] + ",0"
    copies.append(lines)

    lines = list(clean)
    lines.insert(find(lines, "B,") + 1, "I (1140) QMI8658: QMI8658 initialized successfully")
    copies.append(lines)

    lines = list(clean)
    lines.insert(find(lines, "POWER "), boot_line(BOOT_ID + 1))
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "B,")
    lines[i] = lines[i][:-1] + ("0" if lines[i][-1] != "0" else "1")
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "SENSOR_MINUTE ", last=True)
    lines[i] = lines[i].replace("record_drops=0", "record_drops=1")
    copies.append(lines)

    lines = list(clean)
    i = find(lines, "USB_MINUTE ", last=True)
    lines[i] = lines[i].replace("port_drops=0", "port_drops=1")
    copies.append(lines)

    lines = list(clean)
    i = find(lines, f"S,0,0,1000000,{RATE_UHZ},")
    lines[i] = lines[i].replace(str(RATE_UHZ), str(RATE_UHZ + 100))
    copies.append(lines)

    lines = list(clean)
    del lines[find(lines, "W,0,30,")]
    copies.append(lines)

    assert len(copies) == 11
    for n, lines in enumerate(copies):
        assert lines != clean, n
        assert judge(lines, tmp_path)[0] == 1, n


def test_rom_lines_before_boot(tmp_path: Path) -> None:
    """Case 3 puts the first ten lines of pipeline_log.txt before the B line."""
    rom = [line.split("\t", 1)[1] for line in PIPELINE_LOG.read_text().splitlines()[:10]]
    clean = clean_log()
    lines = rom + clean[find(clean, "B,") :]
    code, report = judge(lines, tmp_path)
    assert code == 0, report
    assert "- The log holds 10 lines before the B line." in report


def test_type_hints_and_rules() -> None:
    """Case 4 checks the type hints and the Python rules in the scripts and their tests."""
    for path in SCRIPTS + TEST_FILES:
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                if node.args.vararg is not None:
                    args.append(node.args.vararg)
                if node.args.kwarg is not None:
                    args.append(node.args.kwarg)
                assert all(arg.annotation is not None for arg in args), f"{path.name}: {node.name}"
                assert node.returns is not None, f"{path.name}: {node.name}"
    for path in SCRIPTS:
        source = path.read_text()
        assert "print(" not in source, path.name
        assert "os.path" not in source, path.name
        assert "except Exception" not in source, path.name
        assert not any(line.startswith("import serial") for line in source.splitlines()), path.name
