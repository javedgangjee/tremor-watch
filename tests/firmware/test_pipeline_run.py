"""Tests for tests/firmware/pipeline_run.py.

Each case writes a made-up log and judges it with --log-only and --minutes 3,
so no watch is needed. They run in the reference venv with this command.

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
PIPELINE_RUN = HERE / "pipeline_run.py"
TEST_FILES = (PIPELINE_RUN, HERE / "test_pipeline_run.py", HERE / "test_chip_windows.py")

MINUTES = 3
T0 = 1_000_000
GAP_T0 = 100_000_000
END_US = MINUTES * 60_000_000
GOOD_SETUP = (
    "SENSOR_SETUP ctrl1=0x6C ctrl2=0x26 ctrl3=0x66 ctrl7=0x03 fifo_ctrl=0x0D fifo_wtm=11 "
    "gyro_range_dps=1024 int1_level=0"
)


def load_pipeline_run() -> ModuleType:
    """Import pipeline_run.py from its path."""
    spec = importlib.util.spec_from_file_location("pipeline_run", PIPELINE_RUN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The dataclasses in pipeline_run.py look their module up by name.
    sys.modules["pipeline_run"] = module
    spec.loader.exec_module(module)
    return module


def answer_times(t0: int, first_wait_us: int, until_us: int) -> list[int]:
    """Give the at_us of each window of a stretch. Windows 0 to 5 come together
    after the rate, and then one comes each second."""
    times = [t0 + first_wait_us + 10_000 * n for n in range(6)]
    n = 6
    while t0 + first_wait_us + (n - 5) * 1_000_000 <= until_us:
        times.append(t0 + first_wait_us + (n - 5) * 1_000_000)
        n += 1
    return times


def make_log(gap: bool) -> list[str]:
    """Give a clean 3-minute log, with a stretch end at 100 seconds when gap is true."""
    events: list[tuple[int, str]] = [
        (0, "rst:0x15 (USB_UART_CHIP_RESET),boot:0x2b (SPI_FAST_FLASH_BOOT)"),
        (0, "START uptime_us=65000"),
        (0, "POWER pmu=ok vbus=1 battery=0 battery_mv=0 battery_percent=-1"),
        (0, "TASK name=usb core=0 priority=3"),
        (0, "TASK name=sensor core=1 priority=12"),
        (0, "TASK name=pipeline core=1 priority=8"),
        (0, "TASK name=state core=0 priority=6"),
        (0, "TASK name=screen core=0 priority=5"),
        (0, "DETECTOR_INIT ok=1"),
        (0, GOOD_SETUP),
        (
            T0,
            f"STRETCH number=0 first=0 t0_us={T0} kind=start reason=start prev_span_us=0 prev_readings=0 "
            "prev_rate_uhz=0 error_us=none",
        ),
        (T0 + 10_000_000, "RATE number=0 rate_uhz=114330200"),
    ]
    stretches = [(0, T0, 10_100_000, (GAP_T0 - 1 if gap else END_US))]
    if gap:
        events += [
            (
                GAP_T0,
                f"STRETCH number=1 first=11433 t0_us={GAP_T0} kind=2 reason=time prev_span_us=98900000 "
                "prev_readings=11433 prev_rate_uhz=114330200 error_us=4500.0",
            ),
            (GAP_T0, "RATE number=1 rate_uhz=114330000"),
            (GAP_T0 + 1, "GAP stretch=1 changed=1"),
            (GAP_T0 + 2, f"FACE at_us={GAP_T0 + 2} state=3"),
        ]
        stretches.append((1, GAP_T0, 4_100_000, END_US))
    answers: list[tuple[int, int, int, bool]] = []
    for number, t0, wait, until in stretches:
        for n, at in enumerate(answer_times(t0, wait, until)):
            code = 3 if n == 0 else 1
            counted = n > 0 and n % 4 == 0
            face = 3 if n < 2 else 1
            events.append(
                (
                    at,
                    f"ANSWER stretch={number} window={n} code={code} prob=0.0001 below=0.5 peak=7.5 "
                    f"time_us={t0 + 10_000 * (100 * n + 399)} at_us={at} run_us=6870 delay_us=12400 "
                    f"counted={int(counted)} face={face}",
                )
            )
            if n == 2:
                events.append((at + 1, f"FACE at_us={at + 1} state=1"))
            answers.append((at, code, n, counted))

    for minute in range(1, MINUTES + 1):
        at = minute * 60_000_000
        readings = 6860 * minute
        ends = int(gap and at > GAP_T0)
        before = [a for a in answers if a[0] < at]
        still = sum(1 for a in before if a[3])
        faces = sum(1 for t, text in events if text.startswith("FACE") and t < at)
        warming = sum(1 for a in before if a[1] == 3)
        share = "none" if still == 0 else f"{0.0:.6f}"
        events += [
            (
                at + 10,
                f"SENSOR_MINUTE minute={minute} readings={readings} bursts={readings // 11} "
                f"bursts_at_wtm={readings // 11} largest_burst=11 overflow=0 full=0 read_error=0 stall=0 late=0 "
                f"msg_drops=0 largest_delay_us=4000 stretches={1 + ends} kind1_ends=0 kind2_ends={ends} pipeline=0",
            ),
            (
                at + 20,
                f"PIPELINE_MINUTE minute={minute} readings={readings - 11} breaks=0 "
                "gyro_mean_dps=0.1000,-0.2000,0.0500 gyro_sd_dps=0.0500,0.0500,0.0500 "
                f"accel_mean_counts=10.0,-20.0,4100.0 windows={len(before)} faults=0 end_requests=0 answer_drops=0 "
                "rate_refused=0 run_us_max=7000 delay_us_max=13000 stack_free=1500",
            ),
            (
                at + 30,
                f"STATE_MINUTE minute={minute} answers={len(before)} tremor=0 no_tremor={len(before) - warming} "
                f"moving=0 warming={warming} fault=0 share_tremor=0 share_still={still} share_moving=0 "
                f"share={share} face=1 face_changes={faces} gaps={ends} blocks=1 screen_drops=0 stack_free=2000",
            ),
            (
                at + 40,
                f"SCREEN_MINUTE minute={minute} updates={60 * minute - 1} face=1 face_changes={faces}",
            ),
            (at + 50, f"USB_MINUTE minute={minute} line_drops=0"),
        ]
    events.sort(key=lambda e: e[0])
    return [text for _, text in events]


def judge(lines: list[str], tmp_path: Path) -> tuple[int, str]:
    """Write the lines as a saved log, judge it, and give the exit code and the report."""
    log = tmp_path / "log.txt"
    report = tmp_path / "report.md"
    log.write_text("".join(f"{i * 0.01:.3f}\t{line}\n" for i, line in enumerate(lines)))
    code = load_pipeline_run().main(
        ["--log-only", "--minutes", str(MINUTES), "--log", str(log), "--report", str(report)]
    )
    return code, report.read_text()


def find(lines: list[str], start: str) -> int:
    """Give the place of the first line that starts with some text."""
    return next(i for i, line in enumerate(lines) if line.startswith(start))


def test_clean_log_passes(tmp_path: Path) -> None:
    """Judge the clean log and checks the measurements in the report."""
    code, report = judge(make_log(gap=False), tmp_path)
    assert code == 0, report
    assert "FAIL" not in report
    assert "- The detector run time in microseconds is minimum 6870, median 6870, maximum 6870." in report
    assert "a maximum of 12400" in report
    assert "The gap path did not run on the watch" in report


def test_changed_logs_fail(tmp_path: Path) -> None:
    """Check six changed copies of the clean log."""
    clean = make_log(gap=False)

    lines = list(clean)
    i = find(lines, "ANSWER stretch=0 window=40 ")
    lines.insert(i + 1, lines[i])
    assert judge(lines, tmp_path)[0] == 1

    lines = list(clean)
    i = find(lines, "ANSWER stretch=0 window=50 ")
    lines[i] = lines[i].replace("code=1", "code=2")
    assert judge(lines, tmp_path)[0] == 1

    lines = list(clean)
    i = find(lines, "FACE ")
    lines[i] = lines[i].replace("state=1", "state=0")
    assert judge(lines, tmp_path)[0] == 1

    lines = list(clean)
    lines.insert(find(lines, "ANSWER stretch=0 window=30 "), "END_REQUEST stretch=0 reason=break")
    assert judge(lines, tmp_path)[0] == 1

    lines = list(clean)
    i = find(lines, "ANSWER stretch=0 window=60 ")
    at = int(re.search(r"at_us=(\d+)", lines[i]).group(1))
    lines[i] = lines[i].replace(f"at_us={at}", f"at_us={at + 300_000}")
    assert judge(lines, tmp_path)[0] == 1

    lines = list(clean)
    i = max(i for i, line in enumerate(lines) if line.startswith("STATE_MINUTE "))
    still = int(re.search(r"share_still=(\d+)", lines[i]).group(1))
    lines[i] = lines[i].replace(f"share_still={still}", f"share_still={still + 1}")
    assert judge(lines, tmp_path)[0] == 1


def test_gap_log(tmp_path: Path) -> None:
    """Judge a log whose stretch ends at 100 seconds, with and without its GAP line."""
    lines = make_log(gap=True)
    code, report = judge(lines, tmp_path)
    assert code == 0, report
    assert "The gap path ran on the watch" in report

    lines = [line for line in lines if not line.startswith("GAP ")]
    assert judge(lines, tmp_path)[0] == 1


def test_type_hints() -> None:
    """Check the type hints in pipeline_run.py and the two test files."""
    for path in TEST_FILES:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                if node.args.vararg is not None:
                    args.append(node.args.vararg)
                if node.args.kwarg is not None:
                    args.append(node.args.kwarg)
                assert all(arg.annotation is not None for arg in args), f"{path.name}: {node.name}"
                assert node.returns is not None, f"{path.name}: {node.name}"
