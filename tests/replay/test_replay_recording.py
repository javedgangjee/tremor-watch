"""Tests of replay's recording input, from check 3 of
specs/features/10-laptop-tools/validation.md.

They need the laptop build of replay and the toolbox, so they run in the
reference venv after the C build.

    reference/.venv/bin/python -m pytest tests/replay -q
"""
from __future__ import annotations

import gzip
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tests" / "detector"))
import recording_maker as rm  # noqa: E402
from make_windows import PEAK_STEPS, PSD_FREQS, fine_spectrum  # noqa: E402

FIRMWARE = REPO / "tests" / "firmware"
ROM_LINES = ["ESP-ROM:esp32s3-20210327", "rst:0x15 (USB_UART_CHIP_RESET),boot:0x8 (SPI_FAST_FLASH_BOOT)"]


def log_lines(name: str) -> list[str]:
    """Read a committed log and drop the laptop time and tab of each line."""
    with gzip.open(FIRMWARE / name, "rt", errors="replace") as source:
        return [raw.partition("\t")[2] for raw in source.read().splitlines()]


def w_lines(lines: list[str]) -> list[list[str]]:
    """Give the fields of every W line that has a window."""
    return [line.split(",")[1:] for line in lines if line.startswith("W,") and line.split(",")[2] != ""]


def stretch_one(seconds: float) -> tuple[list[str], rm.Burst, int]:
    """Give case 3's recording with the S line of stretch 1, the burst it starts at, and R1."""
    return rm.with_second_stretch(rm.recording_lines(seconds, 100), 30)


def assert_in_order(rows: pd.DataFrame) -> None:
    """Check that the windows run from 0 with no gap."""
    assert rows["window"].tolist() == list(range(len(rows)))


def test_1_steady_shake_gives_tremor_on_every_window() -> None:
    lines = rm.recording_lines(60, 100)
    at = rm.rate_burst([b for _, b in rm.t_lines(lines)])
    r0 = rm.measured_rate(at.first, at.stamp_us - rm.T0_US)
    rows, stderr, code = rm.replay_rows(lines)
    assert code == 0
    assert (rows["boot"] == rm.BOOT_ID).all()
    assert (rows["stretch"] == 0).all()
    assert (rows["first"] == 0).all()
    assert (rows["t0_us"] == rm.T0_US).all()
    assert (rows["rate_uhz"] == r0).all()
    assert_in_order(rows)
    assert len(rows) >= 50
    assert rows["time_us"].tolist() == [rm.T0_US + 10000 * (100 * w + 399) for w in rows["window"]]
    assert rows["code"].iloc[0] == 3
    assert (rows["code"].iloc[1:] == 0).all()
    counts = rm.summary(stderr)
    assert (counts["bad"], counts["dropped_bursts"], counts["boots"], counts["stretches"]) == (0, 0, 1, 1)


def test_2_clipped_shake_gives_tremor_from_window_1() -> None:
    rows, _, code = rm.replay_rows(rm.recording_lines(60, 1500))
    assert code == 0
    assert np.abs(rm.shake_counts(1500, np.arange(1000), rm.RATE_UHZ)).max() == 32768
    assert (rows["code"].iloc[1:] == 0).all()


def test_3_s_line_ends_the_stretch_as_after_an_overflow() -> None:
    lines, burst, r1 = stretch_one(50)
    rows, stderr, code = rm.replay_rows(lines)
    assert code == 0
    zero = rows[rows["stretch"] == 0]
    one = rows[rows["stretch"] == 1]
    assert len(zero) + len(one) == len(rows)
    assert rows["stretch"].tolist() == sorted(rows["stretch"].tolist())
    assert (zero["first"] == 0).all()
    assert len(one) > 0
    assert (one["first"] == burst.first).all()
    assert (one["t0_us"] == burst.stamp_us).all()
    assert (one["rate_uhz"] == r1).all()
    assert one["window"].tolist() == list(range(len(one)))
    assert one["code"].iloc[0] == 3
    assert rm.summary(stderr)["stretches"] == 2


def test_4_without_the_s_line_the_stretch_goes_on() -> None:
    lines, _, _ = stretch_one(50)
    lines = [line for line in lines if not line.startswith("S,1,")]
    rows, _, code = rm.replay_rows(lines)
    assert code == 0
    assert (rows["stretch"] == 0).all()
    assert_in_order(rows)


def test_5_time_rule_finds_a_drift_end_by_itself() -> None:
    plain = rm.recording_lines(50, 100, shift_from_s=30, shift_us=5000)
    index, burst = rm.t_line_at(plain, 30)
    assert burst.stamp_us == rm.T0_US + round(burst.first * 1e12 / rm.RATE_UHZ) + 5000
    assert 5000 > 0.5 * 1e12 / rm.RATE_UHZ
    before = [b for _, b in rm.t_lines(plain) if b.first < burst.first]
    r1 = rm.stretch_rate(plain, before[0].first, before[-1].first)
    marked = list(plain)
    marked.insert(index, f"S,1,{burst.first},{burst.stamp_us},{r1},1024")
    for lines in (marked, plain):
        rows, _, code = rm.replay_rows(lines)
        assert code == 0
        one = rows[rows["stretch"] == 1]
        assert len(one) > 0
        assert (one["first"] == burst.first).all()
        assert (one["t0_us"] == burst.stamp_us).all()
        assert (one["rate_uhz"] == r1).all()


def test_6_repeated_lines_change_nothing_and_a_new_boot_starts_again() -> None:
    boot1 = rm.recording_lines(20, 100)
    index, _ = rm.t_line_at(boot1, 15)
    latest_s = [line for line in boot1[:index] if line.startswith("S,")][-1]
    boot1[index:index] = [boot1[0], latest_s]
    boot2 = rm.recording_lines(20, 100, boot_id=4294967295, t0_us=300000)
    at = rm.rate_burst([b for _, b in rm.t_lines(boot2)])
    rate2 = rm.measured_rate(at.first, at.stamp_us - 300000)
    lines = boot1 + ["> RESET", *ROM_LINES] + boot2
    rows, stderr, code = rm.replay_rows(lines)
    assert code == 0
    first = rows[rows["boot"] == rm.BOOT_ID]
    assert (first["stretch"] == 0).all()
    assert_in_order(first)
    second = rows[rows["boot"] == 4294967295].reset_index(drop=True)
    assert len(first) + len(second) == len(rows)
    assert second["window"].iloc[0] == 0
    assert (second["stretch"] == 0).all()
    assert (second["first"] == 0).all()
    assert (second["t0_us"] == 300000).all()
    assert (second["rate_uhz"] == rate2).all()
    counts = rm.summary(stderr)
    assert (counts["boots"], counts["stretches"]) == (2, 2)


def test_7_lines_before_b_other_lines_and_a_bad_r_line() -> None:
    lines = rm.recording_lines(30, 100)
    index, broken = rm.t_line_at(lines, 20)
    lines[index + 3] = "R,1234,5"
    place, _ = rm.t_line_at(lines, 5)
    lines[place:place] = ["START uptime_us=1", "> TONE,0", "A,4,0", "W,0,,4,,,", "F,1,3"]
    lines = ["ESP-ROM:esp32s3-20210327", "T,500,11,123", "R,500,1,2,3,4,5,6", *lines]
    rows, stderr, code = rm.replay_rows(lines)
    assert code == 0
    counts = rm.summary(stderr)
    assert (counts["bad"], counts["dropped_bursts"]) == (1, 1)
    bursts = [b for _, b in rm.t_lines(lines) if b.first != 500]
    whole = [b for b in bursts if b.first < broken.first]
    after = next(b for b in bursts if b.first > broken.first)
    zero = rows[rows["stretch"] == 0]
    later = rows[rows["stretch"] != 0]
    assert rows.index[: len(zero)].tolist() == zero.index.tolist()
    assert (zero["first"] == 0).all()
    assert len(later) > 0
    assert (later["first"] == after.first).all()
    assert (later["rate_uhz"] == rm.stretch_rate(lines, whole[0].first, whole[-1].first)).all()


def test_8_samples_file_holds_each_sample_once(tmp_path: Path) -> None:
    out = tmp_path / "samples.csv"
    rows, _, code = rm.replay_rows(rm.recording_lines(60, 100), ["--samples", str(out)])
    assert code == 0
    samples = pd.read_csv(out, float_precision="round_trip")
    k = len(rows)
    assert samples["sample"].tolist() == list(range(100 * (k - 1) + 400))
    assert (samples["boot"] == rm.BOOT_ID).all()
    assert (samples["stretch"] == 0).all()
    window = samples.loc[100:499, ["gyroscope_x", "gyroscope_y", "gyroscope_z"]].to_numpy()
    total = fine_spectrum(window[None, :, :])
    peak = PSD_FREQS[PEAK_STEPS][np.argmax(total[0, PEAK_STEPS])]
    assert peak == 5.0
    assert peak == rows["freq_peak"].iloc[1]


def test_9_file_and_standard_input_agree_and_bad_inputs_fail(tmp_path: Path) -> None:
    lines = rm.recording_lines(60, 100)
    path = tmp_path / "recording.txt"
    path.write_text("".join(line + "\n" for line in lines))
    from_file = subprocess.run([str(rm.REPLAY), "--recording", str(path)], capture_output=True, check=False)
    from_stdin = subprocess.run(
        [str(rm.REPLAY), "--recording", "-"], input=path.read_bytes(), capture_output=True, check=False
    )
    assert from_file.returncode == 0
    assert from_file.stdout == from_stdin.stdout
    no_boot = tmp_path / "no_boot.txt"
    no_boot.write_text("".join(line + "\n" for line in lines if line[0] in "TR"))
    ran = subprocess.run([str(rm.REPLAY), "--recording", str(no_boot)], capture_output=True, text=True, check=False)
    assert ran.returncode == 1
    assert "no B line" in ran.stderr
    missing = subprocess.run(
        [str(rm.REPLAY), "--recording", str(tmp_path / "missing.txt")], capture_output=True, check=False
    )
    assert missing.returncode == 1


def test_10_record_log_matches_the_watch() -> None:
    lines = log_lines("record_log.txt.gz")
    rows, stderr, code = rm.replay_rows(lines)
    assert code == 0
    assert len(rows) == 1798
    assert rows["window"].tolist() == list(range(1798))
    assert (rows["boot"] == 2274443476).all()
    assert (rows["stretch"] == 0).all()
    assert (rows["first"] == 0).all()
    assert (rows["t0_us"] == 234273).all()
    assert (rows["rate_uhz"] == 114347777).all()
    assert rows["time_us"].tolist() == [234273 + 10000 * (100 * w + 399) for w in range(1798)]
    watch = {int(w[1]): w for w in w_lines(lines)}
    for row in rows.itertuples():
        w = watch[row.window]
        assert int(w[2]) == row.code
        assert abs(float(w[3]) - row.pred_tremor_proba) <= 0.0001
    counts = rm.summary(stderr)
    assert (counts["bad"], counts["dropped_bursts"], counts["boots"], counts["stretches"]) == (0, 0, 1, 1)


def test_11_command_log_finds_the_watch_stretches() -> None:
    lines = log_lines("command_log.txt.gz")
    rows, _, code = rm.replay_rows(lines)
    assert code == 0
    assert set(rows["boot"]) == {3162426297, 505078862}
    first = rows[rows["boot"] == 3162426297]
    assert (first["stretch"] == 0).all()
    assert (first["rate_uhz"] == 114348555).all()
    second = rows[rows["boot"] == 505078862]
    assert set(second["stretch"]) == {0, 1}
    assert (second[second["stretch"] == 0]["rate_uhz"] == 114348497).all()
    one = second[second["stretch"] == 1]
    assert (one["first"] == 108185).all()
    assert (one["t0_us"] == 946328952).all()
    assert (one["rate_uhz"] == 114349025).all()
    without, _, code = rm.replay_rows([line for line in lines if not line.startswith("S,1,")])
    assert code == 0
    again = without[(without["boot"] == 505078862) & (without["stretch"] == 1)]
    assert again.reset_index(drop=True).equals(one.reset_index(drop=True))
