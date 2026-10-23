"""Tests for tests/detector/make_windows.py and the saved windows it writes.

They need the toolbox, so they run in the reference venv.

    reference/.venv/bin/python -m pytest tests/detector -q
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import signal

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "make_windows.py"
WINDOWS = HERE / "windows.csv"
ANSWERS = HERE / "answers.csv"
CUT_OFF = 0.029570239921802
FS = 100

GROUP_SIZES = {
    "rest": 40, "tremor": 40, "small_tremor": 40, "walk": 40, "walk_plus_tremor": 40,
    "near_prob_tight": 10, "near_prob_above": 15, "near_prob_below": 15,
    "near_below_tight": 10, "near_below_above": 15, "near_below_below": 15,
    "peak_tie_tight": 10, "peak_tie_wide": 10,
    "peak_3.0": 5, "peak_7.0": 5, "peak_7.25": 5, "peak_2.75": 5,
    "zeros": 1, "clipped": 1,
}


@pytest.fixture(scope="module")
def answers() -> pd.DataFrame:
    """Read the committed answers with exact 64-bit values."""
    return pd.read_csv(ANSWERS, float_precision="round_trip")


def test_1_script_makes_the_same_files(tmp_path: Path) -> None:
    subprocess.run([sys.executable, str(SCRIPT), "--out", str(tmp_path)], check=True, capture_output=True)
    assert (tmp_path / "windows.csv").read_bytes() == WINDOWS.read_bytes()
    assert (tmp_path / "answers.csv").read_bytes() == ANSWERS.read_bytes()


def test_2_sizes_and_float32_text(answers: pd.DataFrame) -> None:
    lines = WINDOWS.read_text(encoding="ascii").splitlines()
    assert lines[0] == "gyroscope_x,gyroscope_y,gyroscope_z"
    values = [text for line in lines[1:] for text in line.split(",")]
    assert len(lines) - 1 == 128_800
    assert len(values) == 128_800 * 3
    assert all(str(np.float32(text)) == text for text in values)
    assert len(answers) == 322
    assert answers["window"].tolist() == list(range(322))
    assert answers["group"].value_counts().to_dict() == GROUP_SIZES


def test_3_tuned_windows_lie_in_their_bands(answers: pd.DataFrame) -> None:
    prob = answers["pred_tremor_proba"] - CUT_OFF
    below = answers["below_tremor_power"] - 50.0
    gap = answers["peak_gap"]
    bands = {
        "near_prob_tight": (prob.abs(), 1e-6, 5e-5),
        "near_prob_above": (prob, 2e-4, 1e-3),
        "near_prob_below": (-prob, 2e-4, 1e-3),
        "near_below_tight": (below.abs(), 1e-4, 2.5e-3),
        "near_below_above": (below, 0.01, 0.05),
        "near_below_below": (-below, 0.01, 0.05),
        "peak_tie_tight": (gap, 1e-6, 5e-5),
        "peak_tie_wide": (gap, 2e-4, 1e-3),
    }
    for group, (value, near, far) in bands.items():
        found = value[answers["group"] == group]
        assert len(found) == GROUP_SIZES[group]
        assert ((found >= near) & (found <= far)).all(), group

    peak_ok = answers["freq_peak"].between(3.0, 7.0)
    rest = answers["pred_arm_at_rest"] == 1
    yes = answers["pred_tremor_proba"] >= CUT_OFF
    for group in ["near_prob_tight", "near_prob_above", "near_prob_below"]:
        chosen = answers["group"] == group
        assert (peak_ok & rest)[chosen].all(), group
    for group in ["near_below_tight", "near_below_above", "near_below_below"]:
        chosen = answers["group"] == group
        assert (peak_ok & yes)[chosen].all(), group
    for group in ["peak_tie_tight", "peak_tie_wide"]:
        chosen = answers["group"] == group
        assert (yes & rest)[chosen].all(), group
    for freq, needs_rest in [(3.0, True), (7.0, True), (7.25, True), (2.75, False)]:
        chosen = answers["group"] == f"peak_{freq}"
        assert (answers["freq_peak"] == freq)[chosen].all()
        assert yes[chosen].all()
        if needs_rest:
            assert rest[chosen].all()


def test_4_welch_peak_is_freq_peak(answers: pd.DataFrame) -> None:
    readings = pd.read_csv(WINDOWS, float_precision="round_trip").to_numpy(dtype=np.float64)
    data = readings.astype(np.float32).astype(np.float64).reshape(322, 400, 3)
    window = signal.get_window("hann", 300, fftbins=False)
    freqs, psd = signal.welch(x=data, fs=FS, window=window, nperseg=300, noverlap=int(300 * 0.8), nfft=400,
                              detrend=False, scaling="density", axis=1)
    total = np.sum(psd, axis=-1)
    band = (freqs >= 1) & (freqs <= 25)
    peaks = freqs[band][np.argmax(total[:, band], axis=1)]
    np.testing.assert_array_equal(peaks, answers["freq_peak"].to_numpy())
    assert (answers["peak_gap"] >= 0).all()


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
