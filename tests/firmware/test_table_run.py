"""Tests for tests/firmware/table_run.py.

Each case writes a made-up log and judges it with --log-only, so no watch is
needed. They run in the reference venv with this command.

    reference/.venv/bin/python -m pytest tests/firmware -q
"""
from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
TABLE_RUN = HERE / "table_run.py"
MODEL_TEST = HERE.parent / "model" / "test_model_copy.py"

GOOD_SETUP = (
    "SENSOR_SETUP ctrl1=0x6C ctrl2=0x26 ctrl3=0x66 ctrl7=0x03 fifo_ctrl=0x0D fifo_wtm=11 "
    "gyro_range_dps=1024 int1_level=0"
)


def load_table_run() -> ModuleType:
    """Import table_run.py from its path."""
    spec = importlib.util.spec_from_file_location("table_run", TABLE_RUN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The dataclasses in table_run.py look their module up by name.
    sys.modules["table_run"] = module
    spec.loader.exec_module(module)
    return module


def clean_lines() -> list[str]:
    """Give a clean log of 3 minutes with two ends of the second kind."""
    lines = [
        "rst:0x15 (USB_UART_CHIP_RESET),boot:0x2b (SPI_FAST_FLASH_BOOT)",
        "START uptime_us=65000",
        "POWER pmu=ok vbus=1 battery=0 battery_mv=0 battery_percent=-1",
        "TASK name=usb core=0 priority=3",
        "TASK name=sensor core=1 priority=12",
        "TASK name=pipeline core=1 priority=8",
        "TASK name=state core=0 priority=6",
        "TASK name=screen core=0 priority=5",
        GOOD_SETUP,
        "STRETCH number=0 first=0 t0_us=1000000 kind=start reason=start prev_span_us=0 prev_readings=0 "
        "prev_rate_uhz=0 error_us=none",
        "RATE number=0 rate_uhz=114330200",
        "STRETCH number=1 first=6860 t0_us=61000000 kind=2 reason=time prev_span_us=59904000 prev_readings=6860 "
        "prev_rate_uhz=114330200 error_us=4500.0",
        "RATE number=1 rate_uhz=114330000",
        "STRETCH number=2 first=17150 t0_us=151000000 kind=2 reason=time prev_span_us=89904000 prev_readings=10290 "
        "prev_rate_uhz=114330000 error_us=-4400.5",
        "RATE number=2 rate_uhz=114329800",
    ]
    for minute in range(1, 4):
        readings = 6860 * minute
        lines += [
            f"SENSOR_MINUTE minute={minute} readings={readings} bursts={readings // 11} "
            f"bursts_at_wtm={readings // 11} largest_burst=11 overflow=0 full=0 read_error=0 stall=0 late=0 "
            f"msg_drops=0 largest_delay_us=4000 stretches=3 kind1_ends=0 kind2_ends=2",
            f"PIPELINE_MINUTE minute={minute} readings={readings - 11} breaks=0 "
            "gyro_mean_dps=0.1000,-0.2000,0.0500 gyro_sd_dps=0.0500,0.0500,0.0500 "
            "accel_mean_counts=10.0,-20.0,4100.0",
            f"SCREEN_MINUTE minute={minute} updates={60 * minute - 1}",
            f"USB_MINUTE minute={minute} line_drops=0",
        ]
    return lines


def judge(lines: list[str], tmp_path: Path) -> tuple[int, str]:
    """Write the lines as a saved log, judge it, and give the exit code and the report."""
    log = tmp_path / "log.txt"
    report = tmp_path / "report.md"
    log.write_text("".join(f"{i * 0.1:.3f}\t{line}\n" for i, line in enumerate(lines)))
    code = load_table_run().main(["--log-only", "--minutes", "3", "--log", str(log), "--report", str(report)])
    return code, report.read_text()


def check_lines(report: str) -> dict[str, bool]:
    """Give each check in the report with True when it passed."""
    return {m.group(2): m.group(1) == "PASS" for m in re.finditer(r"^- (PASS|FAIL): ([^.]+)\.", report, re.M)}


def test_clean_log_passes(tmp_path: Path) -> None:
    """Judge a clean log and checks the counts and the lengths."""
    code, report = judge(clean_lines(), tmp_path)
    assert code == 0
    assert all(check_lines(report).values())
    assert "- Ends of the first kind: 0" in report
    assert "- Ends of the second kind: 2" in report
    assert "| 0 | 0.000 | 59.904 | 114330200 | kind 2 time | 4500.0 |" in report
    assert "| 1 | 60.000 | 89.904 | 114330000 | kind 2 time | -4400.5 |" in report
    assert "| 2 | 150.000 | open | 114329800 | open |  |" in report


def test_loss_fails(tmp_path: Path) -> None:
    """Add an end of the first kind and checks that only the loss check fails."""
    lines = clean_lines()
    lines.insert(
        lines.index("RATE number=2 rate_uhz=114329800") + 1,
        "STRETCH number=3 first=20000 t0_us=176000000 kind=1 reason=overflow prev_span_us=24900000 "
        "prev_readings=2850 prev_rate_uhz=114329800 error_us=none",
    )
    code, report = judge(lines, tmp_path)
    assert code == 1
    results = check_lines(report)
    assert results.pop("no losses") is False
    assert all(results.values())


def test_rate_and_restart_fail(tmp_path: Path) -> None:
    """Check a rate 1100 parts per million high and a second START line."""
    lines = clean_lines()
    lines[lines.index("RATE number=2 rate_uhz=114329800")] = "RATE number=2 rate_uhz=114456000"
    code, _ = judge(lines, tmp_path)
    assert code == 1

    lines = clean_lines()
    lines.append("START uptime_us=65000")
    code, _ = judge(lines, tmp_path)
    assert code == 1


def test_python_rules() -> None:
    """Check the Python style rules in table_run.py and test_model_copy.py."""
    for path in (TABLE_RUN, MODEL_TEST):
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                assert all(arg.annotation is not None for arg in args), f"{path.name}: {node.name}"
                assert node.returns is not None, f"{path.name}: {node.name}"
        assert "print(" not in source
        assert "os.path" not in source
        assert "except Exception" not in source
    assert not any(line.startswith("import serial") for line in TABLE_RUN.read_text().splitlines())
