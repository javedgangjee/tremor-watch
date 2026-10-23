"""Check that the toolbox's aggregate_tremor() gives the shares that tests/share/test_share.c expects.

These tests need the toolbox, so they run in the reference venv.
"""
from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from paradigma.config import TremorConfig
from paradigma.pipelines.tremor_pipeline import aggregate_tremor

HERE = Path(__file__).resolve()
START = pd.Timestamp("2026-10-22 00:00:00")
WINDOW_SECONDS = 4
# The counts of tremor, no tremor, and arm moving windows, and the share that test_share case 3 expects.
COUNT_SETS: list[tuple[int, int, int, float]] = [
    (3, 5, 2, 37.5),
    (2, 4, 1, 33.33333333333333),
    (2, 7, 0, 22.22222222222222),
    (4, 0, 3, 100.0),
    (0, 6, 2, 0.0),
]


def window_table(tremor: int, no_tremor: int, moving: int) -> pd.DataFrame:
    """Build one row per window, 4 seconds apart, with the tremor power 1, 2, 3, and up.

    Tremor windows come first, then no tremor windows, then arm moving windows. Every tremor window
    has a different tremor power, because the toolbox's power summary fails on equal values.
    """
    n = tremor + no_tremor + moving
    at_rest = np.r_[np.ones(tremor + no_tremor, dtype=int), np.zeros(moving, dtype=int)]
    checked = np.r_[np.ones(tremor, dtype=int), np.zeros(no_tremor + moving, dtype=int)]
    return pd.DataFrame({
        "time_dt": START + pd.to_timedelta(np.arange(n) * WINDOW_SECONDS, unit="s"),
        "pred_arm_at_rest": at_rest,
        "pred_tremor_checked": checked,
        "tremor_power": np.arange(1, n + 1, dtype=float),
    })


def test_1_share_matches_test_share() -> None:
    for tremor, no_tremor, moving, share in COUNT_SETS:
        result = aggregate_tremor(window_table(tremor, no_tremor, moving), TremorConfig())
        got = result["aggregated_tremor_measures"]["perc_windows_tremor"]
        assert got == share, (tremor, no_tremor, moving, got)


def test_2_arm_moving_only_raises_warning() -> None:
    with pytest.raises(Warning):
        aggregate_tremor(window_table(0, 0, 5), TremorConfig())


def test_3_python_rules() -> None:
    source = HERE.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            every = [*args.posonlyargs, *args.args, *args.kwonlyargs]
            every += [a for a in (args.vararg, args.kwarg) if a is not None]
            for arg in every:
                assert arg.annotation is not None, f"{node.name} argument {arg.arg}"
            assert node.returns is not None, node.name
    # The banned words are split, so this check does not find itself.
    for banned in ("pri" + "nt(", "os." + "path", "except " + "Exception"):
        assert banned not in source, banned
