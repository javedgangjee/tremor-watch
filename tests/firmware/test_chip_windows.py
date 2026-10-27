"""Tests for tests/firmware/windows_bin.py and tests/firmware/chip_windows.py.

The log cases write a made-up log and judge it with --log-only, so no watch is
needed. They run in the reference venv with this command.

    reference/.venv/bin/python -m pytest tests/firmware -q
"""
from __future__ import annotations

import ast
import importlib.util
import logging
import sys
import zlib
from fractions import Fraction
from pathlib import Path
from types import ModuleType

import numpy as np

HERE = Path(__file__).resolve().parent
WINDOWS_BIN = HERE / "windows_bin.py"
CHIP_WINDOWS = HERE / "chip_windows.py"
PIPELINE_RUN = HERE / "pipeline_run.py"
WINDOWS_CSV = HERE.parent / "detector" / "windows.csv"
ANSWERS_CSV = HERE.parent / "detector" / "answers.csv"

LOG = logging.getLogger("test_chip_windows")


def load(path: Path) -> ModuleType:
    """Import a script from its path."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The dataclasses in the scripts look their module up by name.
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def test_windows_bytes() -> None:
    """Check the bytes and every value that lies near a halfway point."""
    data = load(WINDOWS_BIN).windows_bytes(WINDOWS_CSV)
    assert len(data) == 1_545_600
    wide = np.loadtxt(WINDOWS_CSV, delimiter=",", skiprows=1, dtype=np.float64).ravel()
    assert data == wide.astype("<f4").tobytes()

    narrow = wide.astype(np.float32)
    up = np.nextafter(narrow, np.float32(np.inf))
    down = np.nextafter(narrow, np.float32(-np.inf))
    # The halfway point of two neighbouring 32-bit floats is exact in 64 bits.
    mid_up = (narrow.astype(np.float64) + up.astype(np.float64)) / 2
    mid_down = (narrow.astype(np.float64) + down.astype(np.float64)) / 2
    steps = 2 * np.spacing(np.abs(wide))
    near = (np.abs(wide - mid_up) <= steps) | (np.abs(wide - mid_down) <= steps)
    texts = [cell for line in WINDOWS_CSV.read_text().splitlines()[1:] for cell in line.split(",")]
    assert len(texts) == wide.size
    for i in np.flatnonzero(near):
        exact = Fraction(texts[i])
        mine = abs(exact - Fraction(float(narrow[i])))
        assert mine <= abs(exact - Fraction(float(up[i]))), texts[i]
        assert mine <= abs(exact - Fraction(float(down[i]))), texts[i]
    LOG.info("checked %d values near a halfway point with exact fractions", int(near.sum()))


def test_rule() -> None:
    """Check the rule of test_detector.c on made-up rows."""
    cw = load(CHIP_WINDOWS)

    def toolbox(prob: float = 0.5, below: float = 10.0, gap: float = 0.5) -> object:
        return cw.Row(mfcc=[0.1 * i for i in range(12)], prob=prob, below=below, peak=5.0, at_rest=1, tremor=1, gap=gap)

    def chip_like(t: object, **changes: object) -> object:
        row = cw.Row(mfcc=list(t.mfcc), prob=t.prob, below=t.below, peak=t.peak, at_rest=t.at_rest, tremor=t.tremor)
        for key, value in changes.items():
            setattr(row, key, value)
        return row

    t = toolbox()
    assert cw.rule(t, chip_like(t)) == []
    assert cw.rule(t, chip_like(t, prob=t.prob + 0.00015)) != []
    mfcc = list(t.mfcc)
    mfcc[6] += 0.00015
    assert cw.rule(t, chip_like(t, mfcc=mfcc)) != []

    t = toolbox(prob=cw.CUT_OFF + 0.00005)
    assert cw.rule(t, chip_like(t, tremor=0)) == []
    t = toolbox(prob=cw.CUT_OFF + 0.0005)
    assert cw.rule(t, chip_like(t, tremor=0)) != []

    t = toolbox(below=50.004)
    assert cw.rule(t, chip_like(t, tremor=0, at_rest=0)) == []
    t = toolbox(below=50.006)
    assert cw.rule(t, chip_like(t, tremor=0, at_rest=0)) != []

    t = toolbox(gap=0.00005)
    assert cw.rule(t, chip_like(t, peak=8.0, tremor=0)) == []
    t = toolbox(gap=0.0002)
    assert cw.rule(t, chip_like(t, peak=8.0, tremor=0)) != []


def good_lines() -> list[str]:
    """Give a log whose two passes hold the toolbox's own numbers."""
    data = load(WINDOWS_BIN).windows_bytes(WINDOWS_CSV)
    cw = load(CHIP_WINDOWS)
    answers = cw.read_answers(ANSWERS_CSV)
    lines = [
        "rst:0x15 (USB_UART_CHIP_RESET),boot:0x2b (SPI_FAST_FLASH_BOOT)",
        f"CHECK_CRC value=0x{zlib.crc32(b'123456789'):08x}",
        f"CHECK_START windows=322 bytes={len(data)} crc32=0x{zlib.crc32(data):08x}",
    ]
    for pass_number in (1, 2):
        for w, a in enumerate(answers):
            mfcc = ",".join(repr(x) for x in a.mfcc)
            logreg = int(a.prob >= cw.CUT_OFF)
            lines.append(
                f"CHECK_WINDOW pass={pass_number} window={w} run_us={6600 + w % 7} mfcc={mfcc} prob={a.prob!r} "
                f"below={a.below!r} peak={a.peak!r} logreg={logreg} at_rest={a.at_rest} tremor={a.tremor}"
            )
    lines.append("CHECK_END runs=644")
    return lines


def judge(lines: list[str], tmp_path: Path) -> int:
    """Write the lines as a saved log, judge it, and give the exit code."""
    log = tmp_path / "log.txt"
    report = tmp_path / "report.md"
    log.write_text("".join(f"{i * 0.01:.3f}\t{line}\n" for i, line in enumerate(lines)))
    code = load(CHIP_WINDOWS).main(["--log-only", "--log", str(log), "--report", str(report)])
    assert report.exists()
    return code


def test_good_log_passes(tmp_path: Path) -> None:
    """Judge a log with the toolbox's own numbers."""
    assert judge(good_lines(), tmp_path) == 0
    assert "Detector run time on the chip" in (tmp_path / "report.md").read_text()


def test_bad_logs_fail(tmp_path: Path) -> None:
    """Check four changed copies of the good log."""
    good = good_lines()

    lines = [line for line in good if not line.startswith("CHECK_WINDOW pass=2 window=17 ")]
    assert judge(lines, tmp_path) == 1

    lines = list(good)
    i = next(i for i, line in enumerate(lines) if line.startswith("CHECK_WINDOW pass=2 window=5 "))
    head, tail = lines[i].split(" prob=", 1)
    lines[i] = f"{head} prob=0{tail}"
    assert judge(lines, tmp_path) == 1

    lines = [line if not line.startswith("CHECK_START ") else line[:-8] + "deadbeef" for line in good]
    assert judge(lines, tmp_path) == 1

    lines = [line if not line.startswith("CHECK_CRC ") else "CHECK_CRC value=0x00000000" for line in good]
    assert judge(lines, tmp_path) == 1


def test_python_rules() -> None:
    """Check the Python style rules in the three scripts."""
    for path in (WINDOWS_BIN, CHIP_WINDOWS, PIPELINE_RUN):
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                assert all(arg.annotation is not None for arg in args), f"{path.name}: {node.name}"
                assert node.returns is not None, f"{path.name}: {node.name}"
        assert "print(" not in source
        assert "os.path" not in source
        assert "except Exception" not in source
        assert not any(line.startswith("import serial") for line in source.splitlines())
