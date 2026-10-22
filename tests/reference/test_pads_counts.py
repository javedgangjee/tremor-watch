"""Tests for reference/pads_counts.py. They need the toolbox, so they run in the reference venv."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "reference"))
import pads_counts as pc  # noqa: E402

FS = 100


def write_recording(path: Path, gyro_dps: np.ndarray) -> Path:
    """Write a made-up PADS file with time, three accelerometer axes in g, and the gyroscope in rad/s."""
    n = len(gyro_dps)
    acc = np.tile([0.0, 0.0, 1.0], (n, 1))
    table = np.column_stack([np.arange(n) / FS, acc, np.radians(gyro_dps)])
    np.savetxt(path, table, delimiter=",", fmt="%.10f")
    return path


def still(n: int, seed: int = 3) -> np.ndarray:
    """Seeded noise of 1 deg/s on each axis plus a 0.3 Hz drift."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FS
    return rng.normal(0, 1.0, (n, 3)) + np.outer(np.sin(2 * np.pi * 0.3 * t), rng.uniform(0.5, 2, 3))


def shake(n: int, seed: int = 3) -> np.ndarray:
    """A 5 Hz shake of 200, 70, and 40 deg/s with 1 deg/s noise, as in the firm 5 Hz case of latency_test.py."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FS
    return np.outer(np.sin(2 * np.pi * 5.0 * t), [200.0, 70.0, 40.0]) + rng.normal(0, 1.0, (n, 3))


def test_1_name_gives_subject_task_wrist() -> None:
    assert pc.parse_name(Path("001_RelaxedTask_LeftWrist.txt")) == ("001", "RelaxedTask", "left")


def test_2_label_gives_group() -> None:
    assert pc.group_of(0) == "healthy"
    assert pc.group_of(1) == "Parkinson's"
    assert pc.group_of(2) == "other movement disorder"
    with pytest.raises(ValueError):
        pc.group_of(3)


def test_3_gyroscope_converts_to_degrees(tmp_path: Path) -> None:
    path = tmp_path / "001_Relaxed_LeftWrist.txt"
    np.savetxt(path, [[0.0, 0.0, 0.0, 1.0, 1.0, -0.5, 0.0]], delimiter=",", fmt="%.10f")
    gyro = pc.read_gyroscope(path)
    np.testing.assert_allclose(gyro[0], [57.29578, -28.64789, 0.0], atol=1e-4)


def test_4_cut_drops_first_50_rows(tmp_path: Path) -> None:
    rows = np.arange(1024, dtype=float)
    path = write_recording(tmp_path / "001_Relaxed_LeftWrist.txt", np.column_stack([rows, rows, rows]))
    kept = pc.cut_start(pc.read_gyroscope(path))
    assert len(kept) == 974
    np.testing.assert_allclose(kept[0], [50.0, 50.0, 50.0], atol=1e-6)


def test_5_still_file_window_count(tmp_path: Path) -> None:
    for rows, windows in [(1024, 2), (2048, 4)]:
        path = write_recording(tmp_path / f"{rows:03d}_Relaxed_LeftWrist.txt", still(rows))
        assert len(pc.process_file(path, "healthy")) == windows


def test_6_shake_fires_on_both_windows(tmp_path: Path) -> None:
    path = write_recording(tmp_path / "001_Relaxed_LeftWrist.txt", shake(1024))
    out = pc.process_file(path, "Parkinson's")
    assert len(out) == 2
    assert out["pred_tremor_checked"].tolist() == [1, 1]


def test_7_still_file_does_not_fire_and_is_at_rest(tmp_path: Path) -> None:
    path = write_recording(tmp_path / "001_Relaxed_LeftWrist.txt", still(1024))
    out = pc.process_file(path, "healthy")
    assert len(out) == 2
    assert out["pred_tremor_checked"].tolist() == [0, 0]
    assert out["pred_arm_at_rest"].tolist() == [1, 1]


def test_8_counts_for_each_wrist_view() -> None:
    windows = pd.DataFrame({
        "subject": ["001"] * 8,
        "group": ["healthy"] * 8,
        "task": ["Relaxed"] * 8,
        "wrist": ["left"] * 4 + ["right"] * 4,
        "window": [0, 1, 2, 3] * 2,
        "pred_tremor_checked": [1, 0, 0, 0, 0, 0, 0, 0],
    })
    counts = pc.count_windows(windows).set_index(["task", "group", "wrist"])
    assert counts.loc[("Relaxed", "healthy", "left"), "share"] == pytest.approx(0.25)
    assert counts.loc[("Relaxed", "healthy", "right"), "share"] == pytest.approx(0.0)
    assert counts.loc[("Relaxed", "healthy", "both"), "share"] == pytest.approx(0.125)


def test_9_subject_with_no_files_counts_22_missing(tmp_path: Path) -> None:
    (tmp_path / "preprocessed").mkdir()
    series = tmp_path / "movement" / "timeseries"
    series.mkdir(parents=True)
    pd.DataFrame({"id": ["001", "002"], "label": [0, 1]}).to_csv(
        tmp_path / "preprocessed" / "file_list.csv", index=False)
    for task in pc.TASKS:
        for wrist in pc.WRISTS:
            write_recording(series / f"002_{task}_{wrist}.txt", still(1024))
    _, counts, n_read, n_missing = pc.run_counts(tmp_path)
    assert n_missing == 22
    assert n_read == 22
    assert len(counts) == 99
