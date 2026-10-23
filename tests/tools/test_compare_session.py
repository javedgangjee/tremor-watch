"""Tests of tools/compare_session.py, from check 5 of
specs/features/10-laptop-tools/validation.md.

They need the toolbox and the laptop build of replay, so they run in the
reference venv after the C build.

    reference/.venv/bin/python -m pytest tests/tools/test_compare_session.py -q
"""
from __future__ import annotations

import gzip
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tests" / "replay"))
sys.path.insert(0, str(REPO / "tests" / "pads"))
sys.path.insert(0, str(REPO / "tests" / "detector"))
import compare_session as cs  # noqa: E402
import make_windows  # noqa: E402
import pads_match  # noqa: E402
import recording_maker as rm  # noqa: E402

ROM_LINES = ["ESP-ROM:esp32s3-20210327", "T,500,11,123", "R,500,1,2,3,4,5,6"]
# A W line comes out a little after the burst that completes its window.
W_DELAY_US = 200_000


def w_line(row: pd.Series) -> str:
    """Write one replay row as the watch writes its W line."""
    return (f"W,{int(row['stretch'])},{int(row['window'])},{int(row['code'])},{float(row['pred_tremor_proba'])!r},"
            f"{float(row['below_tremor_power'])!r},{float(row['freq_peak']):.9g}")


def clean_recording() -> tuple[list[str], rm.Burst, int]:
    """Give case 3's recording of check 3 with W lines from replay's rows, the burst of stretch 1, and R1."""
    lines, burst, r1 = rm.with_second_stretch(rm.recording_lines(50, 100), 30)
    rows, _, code = rm.replay_rows(lines)
    assert code == 0
    out: list[str] = []
    pending = [(int(r["time_us"]), w_line(r)) for _, r in rows.iterrows()]
    for line in lines:
        if line.startswith("T,"):
            stamp = int(line.split(",")[3])
            while pending and pending[0][0] + W_DELAY_US <= stamp:
                out.append(pending.pop(0)[1])
        out.append(line)
    out += [text for _, text in pending]
    return out, burst, r1


@pytest.fixture(scope="module")
def clean() -> tuple[list[str], rm.Burst, int]:
    """Make the clean recording once for the module."""
    return clean_recording()


def run_main(tmp_path: Path, lines: list[str], name: str = "recording.txt") -> tuple[int, str]:
    """Save the lines as text, run main() on them, and give the exit code and the report."""
    path = tmp_path / name
    path.write_text("".join(line + "\n" for line in lines))
    report = tmp_path / f"{name}.md"
    code = cs.main([str(path), "--report", str(report)])
    return code, report.read_text() if report.exists() else ""


def compared_count(report: str) -> int:
    """Read the number of windows that the report compared with replay."""
    found = re.search(r"The run compared (\d+) windows", report)
    assert found is not None, report
    return int(found.group(1))


def replace_w(lines: list[str], stretch: int, window: int, field: int, value: str) -> list[str]:
    """Give the lines with one field of one W line replaced."""
    out = list(lines)
    prefix = f"W,{stretch},{window},"
    i = next(i for i, line in enumerate(out) if line.startswith(prefix))
    fields = out[i].split(",")
    fields[field] = value
    out[i] = ",".join(fields)
    return out


def test_22_limits_equal_the_pads_match() -> None:
    assert (cs.LIMIT, cs.PROB_NEAR, cs.BELOW_NEAR, cs.GAP_NEAR) == (
        pads_match.LIMIT, pads_match.PROB_NEAR, pads_match.BELOW_NEAR, pads_match.GAP_NEAR)
    assert (cs.LIMIT, cs.PROB_NEAR, cs.BELOW_NEAR, cs.GAP_NEAR) == (0.0001, 0.0001, 0.005, 0.0001)
    assert cs.CUT_OFF == make_windows.CUT_OFF
    assert abs(cs.CUT_OFF - 0.029570239921802) < 1e-15


def test_23_match_rule() -> None:
    def replay(**changes: float) -> dict[str, float]:
        row = {"pred_tremor_proba": 0.5, "below_tremor_power": 10.0, "freq_peak": 5.0, "code": 0}
        row.update(changes)
        return row

    assert cs.match_window(replay(), replay(), 0.5).passed
    assert cs.match_window(replay(), replay(pred_tremor_proba=0.50009), 0.5).passed
    assert not cs.match_window(replay(), replay(pred_tremor_proba=0.50011), 0.5).passed
    near = cs.CUT_OFF + 0.00005
    assert cs.match_window(replay(pred_tremor_proba=near), replay(pred_tremor_proba=near, code=1), 0.5).passed
    away = cs.CUT_OFF + 0.0002
    assert not cs.match_window(replay(pred_tremor_proba=away), replay(pred_tremor_proba=away, code=1), 0.5).passed
    assert cs.match_window(replay(below_tremor_power=50.004, code=1),
                           replay(below_tremor_power=50.004, code=2), 0.5).passed
    assert not cs.match_window(replay(below_tremor_power=50.006, code=1),
                               replay(below_tremor_power=50.006, code=2), 0.5).passed
    assert cs.match_window(replay(), replay(freq_peak=5.25), 0.00005).passed
    assert not cs.match_window(replay(), replay(freq_peak=5.25), 0.0002).passed


def test_24_spectrum_equals_make_windows() -> None:
    windows = np.random.default_rng(7).random((5, 400, 3))
    total = cs.fine_spectrum(windows)
    assert np.array_equal(total, make_windows.fine_spectrum(windows))
    assert np.array_equal(cs.peak_gaps(total), make_windows.peak_gaps(total))


def test_25_reading_times_of_two_hours() -> None:
    times = cs.reading_times(114330200, 823180)
    assert times.dtype == np.float64
    assert times[0] == 0.0
    assert times[823178] == 823178 * 1e6 / 114330200
    assert abs(times[823178] - 7200.0049) < 1e-4
    assert abs((times[823179] - times[823178]) - 1e6 / 114330200) <= 1e-9


def test_26_toolbox_converts_to_100_a_second(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    real = cs.preprocess_imu_data

    def spy(frame: pd.DataFrame, config: Any, sensor: str, watch_side: str) -> pd.DataFrame:
        out = real(frame, config, sensor=sensor, watch_side=watch_side)
        seen.update(config=config, out=out.reset_index(drop=True), readings=len(frame))
        return out

    monkeypatch.setattr(cs, "preprocess_imu_data", spy)
    readings = np.arange(30 * 114330200 // 1_000_000)
    windows = cs.toolbox_windows(rm.shake_counts(100, readings, 114330200), 114330200)
    assert seen["config"].resampling_frequency == 100
    times = seen["out"]["time"].to_numpy()
    assert np.abs(times - np.arange(len(times)) * 0.01).max() <= 1e-9
    assert 2990 < len(times) < 3001
    assert seen["readings"] == 3429
    assert windows["k"].tolist() == list(range(7))
    assert (windows["code"].iloc[1:] == 0).all()


def test_27_clean_recording_passes(tmp_path: Path, clean: tuple[list[str], rm.Burst, int]) -> None:
    lines, burst, r1 = clean
    code, report = run_main(tmp_path, lines)
    assert code == 0
    assert re.search(r"\| 0 \| 0 \| 250000 \| \d+ \| \d+ \| yes, readings 0 to ", report)
    assert re.search(rf"\| 1 \| {burst.first} \| {burst.stamp_us} \| {r1} \| {r1} \| yes, readings ", report)
    assert "0 windows differ in the code, the peak, or the probability." in report
    assert "0 checks failed." in report
    stretch0 = cs.toolbox_windows(rm.shake_counts(100, np.arange(burst.first), rm.RATE_UHZ),
                                  rm.stretch_rate(lines, 0, rm.rate_burst([b for _, b in rm.t_lines(lines)]).first))
    last = rm.t_lines(lines)[-1][1]
    stretch1 = cs.toolbox_windows(
        rm.shake_counts(100, np.arange(burst.first, last.first + last.count), rm.RATE_UHZ), r1)
    # The toolbox compares window k from k = 1 on only where the watch gave window 4k.
    # Stretch 1 ends before the watch's window 16, so its toolbox window k = 4 is left out.
    watch = {(int(f[1]), int(f[2])) for f in (line.split(",") for line in lines if line.startswith("W,"))}
    expected = sum(int(k) >= 1 and (stretch, 4 * int(k)) in watch
                   for stretch, windows in ((0, stretch0), (1, stretch1)) for k in windows["k"])
    assert expected == 9
    assert f"The toolbox's codes agree on {expected} of {expected} windows, which is 100.0 percent." in report
    assert "100.0 percent from the watch's codes and 100.0 percent from the toolbox's codes" in report


def test_28_changed_copies_fail(tmp_path: Path, clean: tuple[list[str], rm.Burst, int]) -> None:
    lines, burst, r1 = clean
    s0_last = max(i for i, line in enumerate(lines) if line.startswith("S,0,"))
    s1 = next(i for i, line in enumerate(lines) if line.startswith("S,1,"))
    w9 = next(line for line in lines if line.startswith("W,0,9,")).split(",")
    rate0 = lines[s0_last].split(",")
    t0_1 = lines[s1].split(",")
    copies = {
        "code": replace_w(lines, 0, 8, 3, "1"),
        "probability": replace_w(lines, 0, 9, 4, repr(float(w9[4]) + 0.001)),
        "removed": [line for line in lines if not line.startswith("W,0,10,")],
        "extra": [*lines, "W,0,40,0,0.5,10.0,5"],
        "rate": [*lines[:s0_last], ",".join([*rate0[:4], str(int(rate0[4]) + 1), rate0[5]]), *lines[s0_last + 1:]],
        "no_s1": [line for line in lines if not line.startswith("S,1,")],
        "t0": [*lines[:s1], ",".join([*t0_1[:3], str(int(t0_1[3]) + 1), *t0_1[4:]]), *lines[s1 + 1:]],
    }
    assert copies["code"] != lines and copies["rate"] != lines and copies["t0"] != lines
    for name, copy in copies.items():
        code, _ = run_main(tmp_path, copy, f"{name}.txt")
        assert code == 1, name


def test_29_gaps_lines_before_b_and_a_missing_last_w_line_pass(
    tmp_path: Path, clean: tuple[list[str], rm.Burst, int]
) -> None:
    lines, _, _ = clean
    index, _ = rm.t_line_at(lines, 20)
    end = index
    for _ in range(3):
        end += 1
        while end < len(lines) and not lines[end].startswith("T,"):
            end += 1
    removed = [line for i, line in enumerate(lines) if not (index <= i < end and line[0] in "TR")]
    assert len(lines) - len(removed) == 3 * 12
    code, report = run_main(tmp_path, removed, "gap.txt")
    assert code == 0
    found = re.search(r"(\d+) windows were not checked because they lie after a checked part that ended at a gap",
                      report)
    assert found is not None and int(found.group(1)) > 0

    _, clean_report = run_main(tmp_path, lines, "clean.txt")
    code, report = run_main(tmp_path, [*ROM_LINES, *lines], "rom.txt")
    assert code == 0
    assert compared_count(report) == compared_count(clean_report)

    last_w = max(i for i, line in enumerate(lines) if line.startswith("W,"))
    code, _ = run_main(tmp_path, [line for i, line in enumerate(lines) if i != last_w], "last.txt")
    assert code == 0


def test_30_gzip_and_text_give_the_same_report(tmp_path: Path, clean: tuple[list[str], rm.Burst, int]) -> None:
    lines, _, _ = clean
    gz = tmp_path / "clean.txt.gz"
    with gzip.open(gz, "wt") as out:
        for i, line in enumerate(lines):
            out.write(f"{i * 0.001:.3f}\t{line}\n")
    code_gz = cs.main([str(gz), "--report", str(tmp_path / "gz.md")])
    code_text, text_report = run_main(tmp_path, lines, "clean.txt")
    assert code_gz == 0 and code_text == 0

    def counts(report: str) -> list[str]:
        return [line for line in report.splitlines() if not line.startswith(("# ", "- The recording is"))]

    assert counts((tmp_path / "gz.md").read_text()) == counts(text_report)
    code, _ = run_main(tmp_path, [line for line in lines if not line.startswith("B,")], "no_boot.txt")
    assert code == 1
