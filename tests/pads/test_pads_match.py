"""Tests for tests/pads/pads_match.py.

They need the toolbox and the laptop build of replay, so they run in the reference
venv after the C build.

    reference/.venv/bin/python -m pytest tests/pads -q
"""
from __future__ import annotations

import ast
import io
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "reference"))
import pads_match as pm  # noqa: E402
from pads_counts import cut_start, read_gyroscope  # noqa: E402

SCRIPT = HERE / "pads_match.py"
REPLAY = REPO / "build" / "core" / "replay"
FS = 100
HEADER = (
    "window," + ",".join(f"mfcc_{i}" for i in range(1, 13))
    + ",pred_tremor_proba,below_tremor_power,freq_peak,pred_arm_at_rest,pred_tremor_checked"
)


def toolbox_row(**changes: float) -> dict[str, float]:
    """Return a toolbox row with the default values of the test cases, changed as asked."""
    row = {f"mfcc_{i}": 0.1 * i for i in range(1, 13)}
    row.update(pred_tremor_proba=0.5, below_tremor_power=10.0, freq_peak=5.0, peak_gap=0.5,
               pred_arm_at_rest=1, pred_tremor_checked=1)
    row.update(changes)
    return row


def c_row(toolbox: dict[str, float], **changes: float) -> dict[str, float]:
    """Return a C row equal to the toolbox row, changed as asked."""
    row = {key: value for key, value in toolbox.items() if key != "peak_gap"}
    row.update(changes)
    return row


def test_1_equal_rows_pass() -> None:
    tb = toolbox_row()
    assert pm.match_window(tb, c_row(tb)).passed


def test_2_probability_off_by_more_than_the_limit_fails() -> None:
    tb = toolbox_row()
    assert not pm.match_window(tb, c_row(tb, pred_tremor_proba=0.5 + 0.00015)).passed


def test_3_number_off_by_more_than_the_limit_fails() -> None:
    tb = toolbox_row()
    assert not pm.match_window(tb, c_row(tb, mfcc_7=tb["mfcc_7"] + 0.00015)).passed


def test_4_tremor_answer_may_differ_near_the_cut_off() -> None:
    tb = toolbox_row(pred_tremor_proba=pm.CUT_OFF + 0.00005)
    assert pm.match_window(tb, c_row(tb, pred_tremor_checked=0)).passed


def test_5_tremor_answer_must_agree_away_from_the_cut_off() -> None:
    tb = toolbox_row(pred_tremor_proba=pm.CUT_OFF + 0.0005)
    assert not pm.match_window(tb, c_row(tb, pred_tremor_checked=0)).passed


def test_6_rest_answer_may_differ_only_near_50() -> None:
    near = toolbox_row(below_tremor_power=50.004)
    assert pm.match_window(near, c_row(near, pred_arm_at_rest=0, pred_tremor_checked=0)).passed
    away = toolbox_row(below_tremor_power=50.006)
    assert not pm.match_window(away, c_row(away, pred_arm_at_rest=0, pred_tremor_checked=0)).passed


def test_7_peak_may_differ_only_near_a_tie() -> None:
    tie = toolbox_row(peak_gap=0.00005)
    assert pm.match_window(tie, c_row(tie, freq_peak=8.0, pred_tremor_checked=0)).passed
    clear = toolbox_row(peak_gap=0.0002)
    assert not pm.match_window(clear, c_row(clear, freq_peak=8.0, pred_tremor_checked=0)).passed


def test_8_replay_matches_toolbox_on_a_made_up_file(tmp_path: Path) -> None:
    if not REPLAY.is_file():
        pytest.fail(f"replay is not at {REPLAY}. Build it first with cmake.")
    n = 1050
    rng = np.random.default_rng(8)
    t = np.arange(n) / FS
    gyro = np.outer(np.sin(2 * np.pi * 5.0 * t), [0.5, 0.2, 0.1]) + rng.normal(0, 0.02, (n, 3))
    table = np.column_stack([t, np.tile([0.0, 0.0, 1.0], (n, 1)), gyro])
    path = tmp_path / "001_Relaxed_LeftWrist.txt"
    np.savetxt(path, table, delimiter=",", fmt="%.10f")

    ran = subprocess.run([str(REPLAY), "--pads", str(path)], capture_output=True, text=True, check=True)
    assert ran.stdout.splitlines()[0] == HEADER
    c = pd.read_csv(io.StringIO(ran.stdout), float_precision="round_trip")
    assert c["window"].tolist() == list(range(7))

    tb = pm.toolbox_rows(cut_start(read_gyroscope(path)))
    assert len(tb) == 2
    for k in range(2):
        assert pm.match_window(tb.iloc[k], c.iloc[4 * k]).passed


def test_9_python_rules() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            every = [*args.posonlyargs, *args.args, *args.kwonlyargs]
            every += [a for a in (args.vararg, args.kwarg) if a is not None]
            for arg in every:
                assert arg.annotation is not None, f"{node.name} argument {arg.arg}"
            assert node.returns is not None, node.name
    assert "print(" not in source
    assert "os.path" not in source
    assert "except Exception" not in source
