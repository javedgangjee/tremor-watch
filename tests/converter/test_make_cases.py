"""Tests for tests/converter/make_cases.py and the saved converter cases it writes.

They need the toolbox, so they run in the reference venv.

    reference/.venv/bin/python -m pytest tests/converter -q
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "make_cases.py"
FILES = ["stretches.csv", "readings.csv", "expected.csv"]
AXES = ["gyroscope_x", "gyroscope_y", "gyroscope_z"]
STRETCHES = {
    "mix_114": 114330200, "mix_50": 50000000, "mix_100": 100000000, "mix_150": 150000000,
    "shake_clipped": 114330200, "noise": 114330200, "above_50hz": 114330200, "zeros": 114330200,
}


@pytest.fixture(scope="module")
def stretches() -> pd.DataFrame:
    return pd.read_csv(HERE / "stretches.csv")


@pytest.fixture(scope="module")
def readings() -> pd.DataFrame:
    """Read the committed readings with exact 64-bit values."""
    return pd.read_csv(HERE / "readings.csv", float_precision="round_trip")


@pytest.fixture(scope="module")
def expected() -> pd.DataFrame:
    """Read the committed toolbox samples with exact 64-bit values."""
    return pd.read_csv(HERE / "expected.csv", float_precision="round_trip")


def test_1_script_makes_the_same_files(tmp_path: Path) -> None:
    subprocess.run([sys.executable, str(SCRIPT), "--out", str(tmp_path)], check=True, capture_output=True)
    for name in FILES:
        assert (tmp_path / name).read_bytes() == (HERE / name).read_bytes(), name


def test_2_stretches_and_readings(stretches: pd.DataFrame, readings: pd.DataFrame) -> None:
    assert stretches["stretch"].tolist() == list(range(8))
    assert dict(zip(stretches["name"], stretches["rate_uhz"], strict=True)) == STRETCHES
    for row in stretches.itertuples():
        assert row.readings == 30 * row.rate_uhz // 1_000_000
        assert int((readings["stretch"] == row.stretch).sum()) == row.readings
    counts = readings[AXES].to_numpy() * 32
    assert np.array_equal(counts, np.round(counts))
    assert counts.min() >= -32768
    assert counts.max() <= 32767
    zeros = int(stretches.loc[stretches["name"] == "zeros", "stretch"].iloc[0])
    assert (readings.loc[readings["stretch"] == zeros, AXES].to_numpy() == 0).all()


def test_3_sample_numbers_and_counts(stretches: pd.DataFrame, expected: pd.DataFrame) -> None:
    for row in stretches.itertuples():
        samples = expected.loc[expected["stretch"] == row.stretch, "sample"].to_numpy()
        t_last = (row.readings - 1) * 1e6 / row.rate_uhz
        assert len(samples) == len(np.arange(0, t_last, 0.01)), row.name
        assert np.array_equal(samples, np.arange(len(samples))), row.name


def test_4_mix_100_keeps_the_readings(
    stretches: pd.DataFrame, readings: pd.DataFrame, expected: pd.DataFrame,
) -> None:
    index = int(stretches.loc[stretches["name"] == "mix_100", "stretch"].iloc[0])
    values = readings.loc[readings["stretch"] == index, AXES].to_numpy()
    samples = expected.loc[expected["stretch"] == index, AXES].to_numpy()
    assert np.abs(samples - values[: len(samples)]).max() <= 1e-9


def test_5_python_rules() -> None:
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
