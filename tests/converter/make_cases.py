"""Make the saved converter cases with the toolbox's conversion to 100 readings a second.

Run it from the repo root in the reference venv. Fixed seeds make every run write the same files.

    reference/.venv/bin/python tests/converter/make_cases.py

stretches.csv has one row per stretch, readings.csv one row per reading, and
expected.csv one row per toolbox sample. Each 30 second stretch goes to
preprocess_imu_data as its own recording. Every reading is whole raw counts
divided by 32, so it is exact in a 32-bit float. Reading n lies at
n * 1e6 / rate_uhz seconds after the stretch's t0, unrounded.
"""
from __future__ import annotations

import argparse
import logging
import sys
import warnings
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import numpy as np
import pandas as pd
from paradigma.config import IMUConfig
from paradigma.preprocessing import preprocess_imu_data

logger = logging.getLogger("make_cases")

DEFAULT_OUT = Path(__file__).resolve().parent
AXES = ["gyroscope_x", "gyroscope_y", "gyroscope_z"]
OUT_HZ = 100
SECONDS = 30
# Raw counts per degree per second at the 1024 dps range.
COUNTS_PER_DPS = 32
COUNT_MIN = -32768
COUNT_MAX = 32767
# The toolbox's sample k must lie at k * 0.01 seconds within this many seconds.
GRID_LIMIT = 1e-9
# The board's rate from firmware/bringup/rate_log.txt, in millionths of a reading per second.
BOARD_RATE_UHZ = 114330200


def fail(message: str) -> NoReturn:
    """Log the reason and stop the run with exit code 1."""
    logger.error(message)
    sys.exit(1)


def reading_count(rate_uhz: int) -> int:
    """Return the number of readings in a 30 second stretch."""
    return SECONDS * rate_uhz // 1_000_000


def reading_times(rate_uhz: int) -> np.ndarray:
    """Return each reading's time in seconds as 64-bit floats."""
    return np.arange(reading_count(rate_uhz)) * 1e6 / rate_uhz


def sines(t: np.ndarray, freqs: np.ndarray, amps: np.ndarray, phases: np.ndarray) -> np.ndarray:
    """Return the sum of sines over the three axes, shape (len(t), 3).

    freqs has shape (k,), and amps and phases have shape (k, 3).
    """
    angle = 2 * np.pi * t[:, None, None] * freqs[None, :, None] + phases[None, :, :]
    return np.sum(np.sin(angle) * amps[None, :, :], axis=1)


def mix(t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Return 60 background parts from 0.2 to 20 Hz and a tremor burst from 8 to 22 seconds.

    The background is the one in reference/spline_test.py. The burst runs at 4 to 6 Hz
    with 5 to 60 degrees per second on each axis.
    """
    freqs = rng.uniform(0.2, 20, 60)
    amps = rng.uniform(0.5, 2.5, (60, 3))
    phases = rng.uniform(0, 2 * np.pi, (60, 3))
    background = sines(t, freqs, amps, phases)
    tremor_hz = rng.uniform(4, 6, 1)
    tremor_amps = rng.uniform(5, 60, (1, 3))
    on = ((t >= 8) & (t < 22)).astype(float)[:, None]
    return background + sines(t, tremor_hz, tremor_amps, np.zeros((1, 3))) * on


def shake_clipped(t: np.ndarray, rng: np.random.Generator) -> np.ndarray:  # noqa: ARG001
    """Return a 5 Hz shake of 1500, 800, and 300 degrees per second, which the range clips."""
    return sines(t, np.array([5.0]), np.array([[1500.0, 800.0, 300.0]]), np.zeros((1, 3)))


def noise(t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Return random noise with a spread of 200 degrees per second on each axis."""
    return rng.normal(0, 200, (len(t), 3))


def above_50hz(t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Return 45 Hz and 55 Hz parts of up to 100 degrees per second and a 5 Hz part of 30."""
    freqs = np.array([45.0, 55.0, 5.0])
    amps = np.vstack([rng.uniform(50, 100, (2, 3)), np.full((1, 3), 30.0)])
    phases = rng.uniform(0, 2 * np.pi, (3, 3))
    return sines(t, freqs, amps, phases)


def zeros(t: np.ndarray, rng: np.random.Generator) -> np.ndarray:  # noqa: ARG001
    return np.zeros((len(t), 3))


@dataclass(frozen=True)
class Stretch:
    name: str
    rate_uhz: int
    signal: Callable[[np.ndarray, np.random.Generator], np.ndarray]
    seed: int


STRETCHES = [
    Stretch("mix_114", BOARD_RATE_UHZ, mix, 1),
    Stretch("mix_50", 50_000_000, mix, 2),
    Stretch("mix_100", 100_000_000, mix, 3),
    Stretch("mix_150", 150_000_000, mix, 4),
    Stretch("shake_clipped", BOARD_RATE_UHZ, shake_clipped, 5),
    Stretch("noise", BOARD_RATE_UHZ, noise, 6),
    Stretch("above_50hz", BOARD_RATE_UHZ, above_50hz, 7),
    Stretch("zeros", BOARD_RATE_UHZ, zeros, 8),
]


def readings(stretch: Stretch) -> np.ndarray:
    """Return the stretch's readings as whole counts divided by 32, clipped at the range."""
    t = reading_times(stretch.rate_uhz)
    values = stretch.signal(t, np.random.default_rng(stretch.seed))
    counts = np.clip(np.round(values * COUNTS_PER_DPS), COUNT_MIN, COUNT_MAX)
    return counts / COUNTS_PER_DPS


def toolbox(stretch: Stretch, values: np.ndarray) -> pd.DataFrame:
    """Convert one stretch to 100 readings a second with the toolbox, as one recording."""
    frame = pd.DataFrame(values, columns=AXES)
    frame.insert(0, "time", reading_times(stretch.rate_uhz))
    config = IMUConfig()
    config.resampling_frequency = OUT_HZ
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = preprocess_imu_data(frame, config, sensor="gyroscope", watch_side="left")
    return out.reset_index(drop=True)


def check_grid(stretch: Stretch, out: pd.DataFrame) -> None:
    """Stop the run if the toolbox's sample k does not lie at k * 0.01 seconds."""
    times = out["time"].to_numpy()
    gap = np.abs(times - np.arange(len(times)) / OUT_HZ)
    if len(times) == 0 or gap.max() > GRID_LIMIT:
        fail(f"stretch {stretch.name}: the toolbox's grid is not at k * 0.01 seconds")


def number(value: float) -> str:
    """Return the shortest text that gives back the same 64-bit value."""
    return repr(float(value))


def write_files(cases: Sequence[tuple[Stretch, np.ndarray, pd.DataFrame]], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    stretch_lines = ["stretch,name,rate_uhz,readings"]
    reading_lines = ["stretch," + ",".join(AXES)]
    expected_lines = ["stretch,sample," + ",".join(AXES)]
    for index, (stretch, values, out) in enumerate(cases):
        stretch_lines.append(f"{index},{stretch.name},{stretch.rate_uhz},{len(values)}")
        reading_lines += [f"{index}," + ",".join(number(v) for v in row) for row in values]
        samples = out[AXES].to_numpy()
        expected_lines += [f"{index},{k}," + ",".join(number(v) for v in row) for k, row in enumerate(samples)]
    for name, lines in [("stretches.csv", stretch_lines), ("readings.csv", reading_lines),
                        ("expected.csv", expected_lines)]:
        (folder / name).write_text("\n".join(lines) + "\n", encoding="ascii")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Make the saved converter cases.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="the folder for stretches.csv, readings.csv, and expected.csv")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    cases: list[tuple[Stretch, np.ndarray, pd.DataFrame]] = []
    for stretch in STRETCHES:
        values = readings(stretch)
        out = toolbox(stretch, values)
        check_grid(stretch, out)
        cases.append((stretch, values, out))
        logger.info("stretch %s: %d readings, %d samples", stretch.name, len(values), len(out))
    write_files(cases, args.out)
    logger.info("wrote %d stretches to %s", len(cases), args.out)


if __name__ == "__main__":
    main()
