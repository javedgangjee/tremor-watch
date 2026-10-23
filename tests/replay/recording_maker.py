"""Write made-up recordings for the tests of replay's recording input.

A made-up recording holds the lines of core/recording_format.md for one boot.
Its bursts hold 11 readings each, and burst f has the whole-number stamp
t0 + round(f * 1e12 / rate_uhz). The gyroscope holds a shake of A degrees per
second as A * sin(2 * pi * 5 * t) on the x axis, as counts of 32 per degree per
second, rounded and clipped to the 16-bit range, with 0 on y and z. The
accelerometer counts are 0, 0, and 4096.

The file also runs build/core/replay on a list of lines through the standard
input and returns its rows, its summary line, and its exit code.
"""
from __future__ import annotations

import io
import math
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[2]
REPLAY = REPO / "build" / "core" / "replay"
TABLES = REPO / "core" / "detector_tables.h"

BOOT_ID = 305419896
T0_US = 250000
RATE_UHZ = 114330200
BURST = 11
FIRMWARE_VERSION = 9
RESET_CAUSE = 11
RANGE_DPS = 1024
COUNTS_PER_DPS = 32
COUNT_MIN = -32768
COUNT_MAX = 32767
SHAKE_HZ = 5.0
ACCEL = (0, 0, 4096)
# The time rule sets a stretch's rate once its bursts span this long.
RATE_SPAN_US = 10_000_000


@dataclass(frozen=True)
class Burst:
    """One burst: its first reading, its number of readings, and its stamp."""

    first: int
    count: int
    stamp_us: int


def table_hash() -> str:
    """Read DET_MODEL_SHA256 from core/detector_tables.h."""
    found = re.search(r'#define DET_MODEL_SHA256 "([0-9a-f]{64})"', TABLES.read_text(encoding="ascii"))
    assert found is not None, "core/detector_tables.h holds no DET_MODEL_SHA256"
    return found.group(1)


def burst_stamps(
    t0_us: int, rate_uhz: int, seconds: float, shift_from_s: float | None = None, shift_us: int = 0
) -> list[Burst]:
    """Give the bursts of 11 readings whose first reading lies within the seconds.

    Each stamp is t0 + round(first * 1e12 / rate_uhz). With shift_from_s, every
    stamp from the first burst at or after that time on moves shift_us later.
    """
    bursts: list[Burst] = []
    first = 0
    while first * 1e6 / rate_uhz < seconds:
        offset = round(first * 1e12 / rate_uhz)
        if shift_from_s is not None and offset >= shift_from_s * 1e6:
            offset += shift_us
        bursts.append(Burst(first, BURST, t0_us + offset))
        first += BURST
    return bursts


def shake_counts(amplitude: float, readings: np.ndarray, rate_uhz: int) -> np.ndarray:
    """Give the gyroscope counts of a 5 Hz shake on the x axis, shape (n, 3)."""
    t = np.asarray(readings, dtype=np.float64) * 1e6 / rate_uhz
    x = np.clip(np.round(amplitude * np.sin(2 * np.pi * SHAKE_HZ * t) * COUNTS_PER_DPS), COUNT_MIN, COUNT_MAX)
    counts = np.zeros((len(t), 3), dtype=np.int64)
    counts[:, 0] = x.astype(np.int64)
    return counts


def measured_rate(df: int, ds: int) -> int:
    """Give the rate floor(df * 1e12 / ds + 0.5), as the time rule measures it."""
    return math.floor(df * 1e12 / ds + 0.5)


def rate_burst(bursts: Sequence[Burst]) -> Burst:
    """Give the first burst whose stamp is at least 10 seconds after the first burst's."""
    return next(b for b in bursts if b.stamp_us - bursts[0].stamp_us >= RATE_SPAN_US)


def burst_lines(burst: Burst, amplitude: float, rate_uhz: int) -> list[str]:
    """Give the T line of one burst and its R lines."""
    readings = np.arange(burst.first, burst.first + burst.count)
    counts = shake_counts(amplitude, readings, rate_uhz)
    lines = [f"T,{burst.first},{burst.count},{burst.stamp_us}"]
    lines += [
        f"R,{n},{gx},{gy},{gz},{ACCEL[0]},{ACCEL[1]},{ACCEL[2]}"
        for n, (gx, gy, gz) in zip(readings.tolist(), counts.tolist())
    ]
    return lines


def recording_lines(
    seconds: float,
    amplitude: float,
    boot_id: int = BOOT_ID,
    t0_us: int = T0_US,
    rate_uhz: int = RATE_UHZ,
    shift_from_s: float | None = None,
    shift_us: int = 0,
) -> list[str]:
    """Give the B, S, T, and R lines of one boot.

    The first S line gives rate 0. The second S line of stretch 0 gives the
    rate measured from the first burst to the first burst whose stamp is at
    least 10 seconds after t0, and it comes after that burst.
    """
    bursts = burst_stamps(t0_us, rate_uhz, seconds, shift_from_s, shift_us)
    at = rate_burst(bursts)
    rate0 = measured_rate(at.first - bursts[0].first, at.stamp_us - bursts[0].stamp_us)
    lines = [
        f"B,{boot_id},{RESET_CAUSE},{FIRMWARE_VERSION},{table_hash()}",
        f"S,0,0,{t0_us},0,{RANGE_DPS}",
    ]
    for burst in bursts:
        lines += burst_lines(burst, amplitude, rate_uhz)
        if burst == at:
            lines.append(f"S,0,0,{t0_us},{rate0},{RANGE_DPS}")
    return lines


def t_lines(lines: Sequence[str]) -> list[tuple[int, Burst]]:
    """Give the place and the burst of every T line."""
    found: list[tuple[int, Burst]] = []
    for i, line in enumerate(lines):
        if line.startswith("T,"):
            first, count, stamp = (int(v) for v in line.split(",")[1:])
            found.append((i, Burst(first, count, stamp)))
    return found


def t_line_at(lines: Sequence[str], at_s: float, t0_us: int = T0_US) -> tuple[int, Burst]:
    """Give the place and the burst of the first T line at or after at_s seconds from t0."""
    return next((i, b) for i, b in t_lines(lines) if b.stamp_us - t0_us >= at_s * 1e6)


def stretch_rate(lines: Sequence[str], first: int, last: int) -> int:
    """Give the rate measured from the burst at reading `first` to the burst at reading `last`."""
    stamps = {b.first: b.stamp_us for _, b in t_lines(lines)}
    return measured_rate(last - first, stamps[last] - stamps[first])


def with_second_stretch(lines: list[str], at_s: float) -> tuple[list[str], Burst, int]:
    """Put the S line of stretch 1 just before the first T line at or after at_s seconds.

    The stamps stay on time, so only the S line marks the end, as after an
    overflow. The rate R1 comes from the first to the last burst of stretch 0.
    It returns the new lines, the burst that starts stretch 1, and R1.
    """
    index, burst = t_line_at(lines, at_s)
    before = [b for _, b in t_lines(lines) if b.first < burst.first]
    r1 = stretch_rate(lines, before[0].first, before[-1].first)
    changed = list(lines)
    changed.insert(index, f"S,1,{burst.first},{burst.stamp_us},{r1},{RANGE_DPS}")
    return changed, burst, r1


def replay_rows(lines: Sequence[str], args: Sequence[str] = ()) -> tuple[pd.DataFrame, str, int]:
    """Run replay on the lines through the standard input.

    It returns the rows, the standard error, and the exit code.
    """
    if not REPLAY.is_file():
        pytest.fail(f"replay is not at {REPLAY}. Build it first with cmake.")
    text = "".join(line + "\n" for line in lines)
    ran = subprocess.run(
        [str(REPLAY), "--recording", "-", *args], input=text, capture_output=True, text=True, check=False
    )
    rows = pd.read_csv(io.StringIO(ran.stdout), float_precision="round_trip") if ran.stdout else pd.DataFrame()
    return rows, ran.stderr, ran.returncode


def summary(stderr: str) -> dict[str, int]:
    """Read the counts of replay's summary line."""
    found = re.search(r"^replay: (lines=.*)$", stderr, re.MULTILINE)
    assert found is not None, f"no summary line in {stderr!r}"
    return {key: int(value) for key, value in (part.split("=") for part in found.group(1).split())}
