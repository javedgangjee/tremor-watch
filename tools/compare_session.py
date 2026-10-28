"""Compare a recording from the watch with replay and with the toolbox.

The script runs in the reference venv, because it needs the toolbox, and it
needs the laptop build of replay. Run it from the repo root after the C build.

    reference/.venv/bin/python tools/compare_session.py RECORDING [--replay PATH] [--report PATH]

RECORDING is a file that tools/watch_cli.py saved, or any of the logs in
tests/firmware/. A name that ends in .gz is read as gzip text, and any other
name as plain text. A leading laptop time and tab is dropped from each line. A
gzip file that was cut short is read up to the cut, and the report says so.

The script runs replay on the lines and reads the watch's own lines in the
same way. It checks a stretch only where the recording holds all of its T and
R lines from its first reading on. For each checked window from window 1 on,
the probability must agree within 1e-6, the low-frequency sum within a
millionth of its size, and the code and the peak must agree unless replay's
numbers lie near a cut-off. It then runs the toolbox on each
checked part with its conversion set to 100 readings a second and reports how
often the toolbox's code agrees with the watch's. The rules are in
specs/features/10-laptop-tools/requirements.md.

It writes a Markdown report and exits with code 0 only when every check of
the replay comparison passes. The toolbox's agreement and the share have no
pass limit.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import io
import logging
import math
import subprocess
import sys
import tempfile
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import paradigma
from paradigma.classification import ClassifierPackage
from paradigma.config import IMUConfig, TremorConfig
from paradigma.pipelines.tremor_pipeline import detect_tremor, extract_tremor_features
from paradigma.preprocessing import preprocess_imu_data
from scipy import signal

from recording_text import read_recording, record_patterns

logger = logging.getLogger("compare_session")

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REPLAY = REPO / "build" / "core" / "replay"
MODEL_FILE = Path(paradigma.__file__).resolve().parent / "assets" / "tremor_detection_clf_package.pkl"

# The watch and replay run the same C code, so their numbers differ only where
# the chip's maths library and the laptop's differ. On the committed logs the
# probability differs by at most 2.52e-10 and the low-frequency sum not at
# all. On the 322 saved windows of tests/firmware/chip_windows_log.txt, which
# run from no tremor to tremor, the chip and the laptop build differ by at most
# 9.9e-8 in the probability and not at all in the sum. The probability limit
# is ten times that largest difference. The sum is a 32-bit float sum, so its
# limit is relative: a millionth of replay's value is about 16 steps of a
# 32-bit float.
PROB_LIMIT = 1e-6
BELOW_LIMIT = 1e-6
# The margins around the cut-offs, the same as in tests/pads/pads_match.py.
PROB_NEAR = 0.0001
BELOW_NEAR = 0.005
GAP_NEAR = 0.0001
MOVEMENT_THRESHOLD = 50.0
CUT_OFF = float(ClassifierPackage.load(MODEL_FILE).threshold)
# The toolbox's sample k must lie at k * 0.01 seconds within this many seconds.
GRID_LIMIT = 1e-9
OUT_HZ = 100

AXES = ["gyroscope_x", "gyroscope_y", "gyroscope_z"]
COUNTS_PER_DPS = 32
WINDOW_LEN = 400
WINDOW_STEP = 100
# The toolbox cuts a window every 4 seconds, and the watch every second.
TOOLBOX_EVERY = 4

# The fine spectrum's settings, as tests/detector/make_windows.py takes them
# from the toolbox's extract_spectral_domain_features.
PSD_SEG = 300
PSD_OVERLAP = int(PSD_SEG * 0.8)
PSD_NFFT = 400
PEAK_STEPS = slice(4, 101)  # 1 to 25 Hz, both ends included

RES_TREMOR = 0
RES_NO_TREMOR = 1
RES_ARM_MOVING = 2

# The record lines of core/recording_format.md, read from its table as
# tests/firmware/record_run.py reads them.
PATTERNS = record_patterns()
COUNT_MIN = -32768
COUNT_MAX = 32767
BURST_MAX = 256

REASON_GAP = "after a checked part that ended at a gap"
REASON_START = "in a stretch that started before the recording"


class StopRun(Exception):
    """A problem that stops the run with exit code 1."""


@dataclass(frozen=True)
class SLine:
    """The last S line of one stretch number."""

    first: int
    t0_us: int
    rate_uhz: int


@dataclass(frozen=True)
class TLine:
    """One T line whose R lines all came, in order."""

    first: int
    count: int
    stamp_us: int


@dataclass(frozen=True)
class Gap:
    """A gap in the T numbers: the first missing reading and the next T line's first reading."""

    missing: int
    next_first: int


@dataclass
class Boot:
    """The watch's lines of one boot."""

    boot_id: int
    s_lines: dict[int, SLine] = field(default_factory=dict)
    t_lines: list[TLine] = field(default_factory=list)
    counts: dict[int, tuple[int, int, int]] = field(default_factory=dict)
    w_lines: dict[tuple[int, int], dict[str, float]] = field(default_factory=dict)
    w_text: dict[tuple[int, int], str] = field(default_factory=dict)
    gaps: list[Gap] = field(default_factory=list)


@dataclass(frozen=True)
class Part:
    """The checked part of one stretch: its readings from first to last."""

    boot_id: int
    stretch: int
    first: int
    last: int
    t0_us: int
    rate_uhz: int
    ended_at_gap: bool


@dataclass(frozen=True)
class Match:
    """The result of comparing one replay row with the watch's W line."""

    passed: bool
    prob_diff: float
    below_diff: float
    code_differs: bool
    peak_differs: bool
    near_cut_off: bool
    near_tie: bool
    failed: str


def run_replay(replay: Path, lines: list[str], samples: Path) -> tuple[pd.DataFrame, str]:
    """Run replay on the lines with its samples file, and return its rows and its standard error."""
    if not replay.is_file():
        raise StopRun(f"replay is not at {replay}. Build it first with cmake.")
    text = "".join(line + "\n" for line in lines)
    ran = subprocess.run(
        [str(replay), "--recording", "-", "--samples", str(samples)],
        input=text, capture_output=True, text=True, check=False,
    )
    if ran.returncode != 0:
        raise StopRun(f"replay exited with code {ran.returncode}: {ran.stderr.strip()}")
    rows = pd.read_csv(io.StringIO(ran.stdout), float_precision="round_trip")
    return rows, ran.stderr


def record_kind(line: str) -> str:
    """Give the letter of a line that starts with a record letter and a comma, or an empty text."""
    if len(line) >= 2 and line[1] == "," and line[0] in PATTERNS:
        return line[0]
    return ""


def fits(values: Sequence[int], low: int, high: int) -> bool:
    return all(low <= v <= high for v in values)


@dataclass
class Held:
    """A T line that waits for its R lines."""

    line: TLine
    counts: list[tuple[int, int, int]] = field(default_factory=list)
    broken: bool = False


def close_burst(boot: Boot, held: Held | None) -> None:
    """Keep a burst that holds exactly its count of R lines in order, and note a gap before it."""
    if held is None or held.broken or len(held.counts) != held.line.count or held.line.count == 0:
        return
    if boot.t_lines:
        last = boot.t_lines[-1]
        if held.line.first != last.first + last.count:
            boot.gaps.append(Gap(last.first + last.count, held.line.first))
    boot.t_lines.append(held.line)
    for i, counts in enumerate(held.counts):
        boot.counts[held.line.first + i] = counts


def watch_side(lines: list[str]) -> list[Boot]:
    """Read the watch's lines from the first B line on, with the skip rules of replay."""
    boots: list[Boot] = []
    held: Held | None = None
    for line in lines:
        kind = record_kind(line)
        if not kind or (not boots and kind != "B"):
            continue
        found = PATTERNS[kind].match(line)
        if found is None:
            continue
        values = found.groups()
        if kind == "B":
            if boots:
                close_burst(boots[-1], held)
            held = None
            if not boots or int(values[0]) != boots[-1].boot_id:
                boots.append(Boot(int(values[0])))
        elif kind == "S":
            number, first, t0, rate, _ = (int(v) for v in values)
            boots[-1].s_lines[number] = SLine(first, t0, rate)
        elif kind == "T":
            first, count, stamp = (int(v) for v in values)
            if count > BURST_MAX:
                continue
            close_burst(boots[-1], held)
            held = Held(TLine(first, count, stamp))
        elif kind == "R":
            number, *raw = (int(v) for v in values)
            if not fits(raw, COUNT_MIN, COUNT_MAX) or held is None or held.broken:
                continue
            if len(held.counts) >= held.line.count or number != held.line.first + len(held.counts):
                held.broken = True
                continue
            held.counts.append((raw[0], raw[1], raw[2]))
        elif kind == "W" and values[1] != "":
            # The pattern lets a number be empty or malformed. Such a line is
            # skipped, so its window shows as one with no W line.
            try:
                numbers = {
                    "code": float(values[2]),
                    "pred_tremor_proba": float(values[3]),
                    "below_tremor_power": float(values[4]),
                    "freq_peak": float(values[5]),
                }
            except ValueError:
                continue
            key = (int(values[0]), int(values[1]))
            boots[-1].w_lines[key] = numbers
            boots[-1].w_text[key] = values[3]
    if boots:
        close_burst(boots[-1], held)
    return boots


def stretch_ranges(boot: Boot) -> list[tuple[int, int, float]]:
    """Give each stretch number with its first reading and the first reading of the next stretch."""
    numbers = sorted(boot.s_lines)
    ranges: list[tuple[int, int, float]] = []
    for i, number in enumerate(numbers):
        end = boot.s_lines[numbers[i + 1]].first if i + 1 < len(numbers) else math.inf
        ranges.append((number, boot.s_lines[number].first, end))
    return ranges


def checked_parts(boot: Boot) -> list[Part]:
    """Give the checked part of each stretch whose first reading the recording holds.

    The part runs from the stretch's first reading to the first gap in its T
    numbers, or to its end.
    """
    starts = {t.first: i for i, t in enumerate(boot.t_lines)}
    parts: list[Part] = []
    for number, first, end in stretch_ranges(boot):
        if first not in starts:
            continue
        i = starts[first]
        last_t = boot.t_lines[i]
        while i + 1 < len(boot.t_lines):
            nxt = boot.t_lines[i + 1]
            if nxt.first >= end or nxt.first != last_t.first + last_t.count:
                break
            i += 1
            last_t = nxt
        last = last_t.first + last_t.count - 1
        after = boot.t_lines[i + 1] if i + 1 < len(boot.t_lines) else None
        ended_at_gap = after is not None and last + 1 < end and after.first != last + 1
        s = boot.s_lines[number]
        parts.append(Part(boot.boot_id, number, first, last, s.t0_us, s.rate_uhz, ended_at_gap))
    return parts


def match_window(replay_row: Mapping[str, float], watch: Mapping[str, float], peak_gap: float) -> Match:
    """Check one window of replay against the watch's W line.

    The probability must agree within PROB_LIMIT, and the low-frequency sum
    within BELOW_LIMIT times replay's sum. The codes must agree unless
    replay's window lies near a cut-off, and the peaks must agree unless
    replay's two largest peak steps nearly tie. below_diff is the difference
    in the sum divided by replay's sum.
    """
    prob = float(replay_row["pred_tremor_proba"])
    prob_diff = abs(float(watch["pred_tremor_proba"]) - prob)
    below = float(replay_row["below_tremor_power"])
    below_gap = abs(float(watch["below_tremor_power"]) - below)
    below_diff = below_gap / abs(below) if below != 0 else (0.0 if below_gap == 0 else math.inf)
    near_tie = peak_gap < GAP_NEAR
    near_cut_off = (
        abs(prob - CUT_OFF) <= PROB_NEAR
        or abs(float(replay_row["below_tremor_power"]) - MOVEMENT_THRESHOLD) <= BELOW_NEAR
        or near_tie
    )
    code_differs = int(watch["code"]) != int(replay_row["code"])
    peak_differs = float(watch["freq_peak"]) != float(replay_row["freq_peak"])
    failed = []
    if prob_diff > PROB_LIMIT:
        failed.append("probability")
    if below_diff > BELOW_LIMIT:
        failed.append("low-frequency sum")
    if code_differs and not near_cut_off:
        failed.append("code")
    if peak_differs and not near_tie:
        failed.append("peak")
    return Match(not failed, prob_diff, below_diff, code_differs, peak_differs, near_cut_off, near_tie,
                 ", ".join(failed))


def fine_spectrum(windows: np.ndarray) -> np.ndarray:
    """Return the toolbox's fine spectrum with the three axes added, shape (n, 201).

    It calls scipy welch with the same arguments as the toolbox's
    extract_spectral_domain_features, then adds the axes as compute_total_power does.
    """
    window = signal.get_window("hann", PSD_SEG, fftbins=False)
    _, psd = signal.welch(
        x=np.asarray(windows, dtype=np.float64), fs=OUT_HZ, window=window, nperseg=PSD_SEG,
        noverlap=PSD_OVERLAP, nfft=PSD_NFFT, detrend=False, scaling="density", axis=1,
    )
    return np.sum(psd, axis=-1)


def peak_gaps(total: np.ndarray) -> np.ndarray:
    """Return the largest minus the second largest step from 1 to 25 Hz, divided by the largest.

    A spectrum whose largest step is 0 has a gap of 0, because every step ties.
    """
    top = np.sort(total[:, PEAK_STEPS], axis=1)
    largest, second = top[:, -1], top[:, -2]
    return np.divide(largest - second, largest, out=np.zeros_like(largest), where=largest > 0)


def reading_times(rate_uhz: int, count: int) -> np.ndarray:
    """Return the time of each reading in seconds, n * 1e6 / rate_uhz, as 64-bit floats."""
    return np.arange(count) * 1e6 / rate_uhz


def toolbox_code(tremor: np.ndarray, at_rest: np.ndarray) -> np.ndarray:
    """Give the code of each window as res_from_answer() gives it for a window after 0."""
    return np.where(tremor == 1, RES_TREMOR, np.where(at_rest == 1, RES_NO_TREMOR, RES_ARM_MOVING))


def toolbox_windows(counts: np.ndarray, rate_uhz: int) -> pd.DataFrame:
    """Run the toolbox on one checked part as one recording.

    It returns one row per 4 second window with k, the code, the toolbox's
    numbers, and the peak gap from the toolbox's own converted window.
    """
    columns = ["k", "code", "pred_tremor_proba", "below_tremor_power", "freq_peak",
               "pred_arm_at_rest", "pred_tremor_checked", "peak_gap"]
    frame = pd.DataFrame(np.asarray(counts, dtype=np.float64) / COUNTS_PER_DPS, columns=AXES)
    frame.insert(0, "time", reading_times(rate_uhz, len(frame)))
    config = IMUConfig()
    config.resampling_frequency = OUT_HZ
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        converted = preprocess_imu_data(frame, config, sensor="gyroscope", watch_side="left")
    converted = converted.reset_index(drop=True)
    times = converted["time"].to_numpy()
    if len(times) == 0 or np.abs(times - np.arange(len(times)) / OUT_HZ).max() > GRID_LIMIT:
        raise StopRun("the toolbox's converted samples do not lie at k * 0.01 seconds")
    if len(converted) < WINDOW_LEN:
        return pd.DataFrame(columns=columns)
    tremor_config = TremorConfig()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        features = extract_tremor_features(converted, tremor_config)
        out = detect_tremor(features, tremor_config, MODEL_FILE).reset_index(drop=True)
    n = len(out)
    samples = converted[AXES].to_numpy(dtype=np.float64)[: n * WINDOW_LEN].reshape(n, WINDOW_LEN, len(AXES))
    out["peak_gap"] = peak_gaps(fine_spectrum(samples))
    out["k"] = np.arange(n)
    out["code"] = toolbox_code(out["pred_tremor_checked"].to_numpy(), out["pred_arm_at_rest"].to_numpy())
    return out[columns]


def share_of(codes: Sequence[int]) -> float | None:
    """Give the share of still time with tremor, as core/share.h counts it, or None with no still window."""
    tremor = sum(1 for c in codes if c == RES_TREMOR)
    still = tremor + sum(1 for c in codes if c == RES_NO_TREMOR)
    return 100.0 * tremor / still if still else None


@dataclass
class StretchNote:
    """One stretch of the report."""

    boot_id: int
    stretch: str
    first: int
    t0_us: int
    watch_rate: int | None
    replay_rate: int | None
    checked: str


@dataclass
class Differ:
    """One window where the code, the peak, or the probability differs."""

    boot_id: int
    stretch: int
    window: int
    replay: dict[str, float]
    watch: dict[str, float]
    match: Match


@dataclass
class ToolboxDiffer:
    """One window where the toolbox's code differs from the watch's."""

    boot_id: int
    stretch: int
    k: int
    toolbox_code: int
    watch_code: int
    near_cut_off: bool


@dataclass
class Result:
    """Everything the report needs."""

    boots: list[int] = field(default_factory=list)
    stretches: list[StretchNote] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    compared: int = 0
    prob_diff: float = 0.0
    below_diff: float = 0.0
    text_differs: int = 0
    first_window: int | None = None
    last_window: int | None = None
    differs: list[Differ] = field(default_factory=list)
    not_checked: dict[str, int] = field(default_factory=lambda: {REASON_GAP: 0, REASON_START: 0})
    exempt_last: int = 0
    replay_only: int = 0
    toolbox_compared: int = 0
    toolbox_agree: int = 0
    toolbox_prob_diff: float = 0.0
    toolbox_differs: list[ToolboxDiffer] = field(default_factory=list)
    watch_codes: list[int] = field(default_factory=list)
    toolbox_codes: list[int] = field(default_factory=list)
    summary: str = ""
    cut_short: bool = False


def trouble_in(boot: Boot, number: int | None) -> bool:
    """Tell whether a gap in the T numbers or the start of the recording lies in a stretch."""
    if number is None:
        return False
    for stretch, first, end in stretch_ranges(boot):
        if stretch != number:
            continue
        if any(first <= gap.missing < end for gap in boot.gaps):
            return True
        start = boot.t_lines[0].first if boot.t_lines else None
        return start is not None and first < start < end
    return False


def stretch_holding(boot: Boot, reading: int) -> int | None:
    """Give the stretch number whose readings hold a reading, or None."""
    holding = None
    for number, first, _ in stretch_ranges(boot):
        if first <= reading:
            holding = number
    return holding


def stretch_before(boot: Boot, number: int | None) -> int | None:
    lower = [n for n in boot.s_lines if number is not None and n < number]
    return max(lower) if lower else None


def exempt(boot: Boot, number: int | None) -> bool:
    """Tell whether a gap or the start of the recording lies in the stretch or in the one before it."""
    return trouble_in(boot, number) or trouble_in(boot, stretch_before(boot, number))


def sample_windows(samples: pd.DataFrame, windows: np.ndarray) -> np.ndarray:
    """Cut the 100 Hz windows with the given numbers from one stretch's samples, shape (n, 400, 3)."""
    values = samples.sort_values("sample")[AXES].to_numpy(dtype=np.float64)
    index = WINDOW_STEP * windows[:, None] + np.arange(WINDOW_LEN)[None, :]
    return values[index]


def compare_boot(result: Result, boot: Boot, rows: pd.DataFrame, samples: pd.DataFrame, last_of_boot: int | None) -> None:
    """Compare replay with the watch for one boot and run the toolbox on its checked parts."""
    parts = {p.stretch: p for p in checked_parts(boot)}
    boot_rows = rows[rows["boot"] == boot.boot_id]
    replay_stretches = boot_rows.groupby("stretch", sort=True)
    matched: dict[int, int] = {}
    replay_rates: dict[int, int] = {}
    replay_last: dict[int, int] = {}
    for replay_number, group in replay_stretches:
        first, t0, rate = (int(group[c].iloc[0]) for c in ("first", "t0_us", "rate_uhz"))
        number = next((n for n, s in boot.s_lines.items() if s.first == first and s.t0_us == t0), None)
        if number is None:
            holding = stretch_holding(boot, first)
            result.stretches.append(StretchNote(boot.boot_id, f"replay {replay_number}", first, t0, None, rate,
                                                "no, replay starts it with no S line"))
            if exempt(boot, holding):
                result.replay_only += len(group)
            else:
                result.problems.append(
                    f"boot {boot.boot_id}: replay starts a stretch at reading {first} with t0 {t0} that has no S line"
                )
            continue
        replay_rates[number] = rate
        if rate != boot.s_lines[number].rate_uhz:
            if exempt(boot, number):
                # A gap hid readings that the watch took this rate from, so
                # replay cannot rebuild the stretch's windows. They are counted
                # with the windows after a gap and not compared.
                continue
            result.problems.append(
                f"boot {boot.boot_id} stretch {number}: replay's rate {rate} differs from the watch's "
                f"{boot.s_lines[number].rate_uhz}"
            )
        matched[number] = int(replay_number)
        replay_last[number] = int(group["window"].max())

    has_windows = {s for s, _ in boot.w_lines}
    lowest = min([*boot.s_lines, *has_windows], default=None)
    for number, s in sorted(boot.s_lines.items()):
        part = parts.get(number)
        checked = "no"
        if part is not None and number in matched:
            checked = f"yes, readings {part.first} to {part.last}" + (", ended at a gap" if part.ended_at_gap else "")
        elif part is not None and number in has_windows and not exempt(boot, number):
            result.problems.append(f"boot {boot.boot_id} stretch {number}: replay does not start this stretch")
        result.stretches.append(StretchNote(boot.boot_id, str(number), s.first, s.t0_us, s.rate_uhz,
                                            replay_rates.get(number), checked))

    compared: list[tuple[int, int, dict[str, float], dict[str, float]]] = []
    by_key = {(int(r.stretch), int(r.window)): r for r in boot_rows.itertuples(index=False)}
    for (number, window), watch in sorted(boot.w_lines.items()):
        if number in matched:
            row = by_key.get((matched[number], window))
            if row is not None:
                compared.append((number, window, row._asdict(), watch))
            elif parts[number].ended_at_gap and window > replay_last[number]:
                result.not_checked[REASON_GAP] += 1
            else:
                result.problems.append(
                    f"boot {boot.boot_id}: the W line of stretch {number} window {window} has no replay row"
                )
        elif number == lowest and number not in parts:
            result.not_checked[REASON_START] += 1
        elif number in boot.s_lines and exempt(boot, number):
            result.not_checked[REASON_GAP] += 1
        else:
            result.problems.append(
                f"boot {boot.boot_id}: the W line of stretch {number} window {window} has no replay row to compare"
            )

    for number, replay_number in matched.items():
        group = boot_rows[boot_rows["stretch"] == replay_number]
        for window in group["window"].astype(int):
            if (number, window) in boot.w_lines:
                continue
            if last_of_boot is not None and window == last_of_boot and replay_number == int(boot_rows["stretch"].iloc[-1]):
                result.exempt_last += 1
            else:
                result.problems.append(
                    f"boot {boot.boot_id}: replay's stretch {number} window {window} has no W line"
                )

    gaps_by_stretch: dict[int, np.ndarray] = {}
    for number in {n for n, _, _, _ in compared}:
        windows = np.array([w for n, w, _, _ in compared if n == number])
        part_samples = samples[(samples["boot"] == boot.boot_id) & (samples["stretch"] == matched[number])]
        gaps_by_stretch[number] = peak_gaps(fine_spectrum(sample_windows(part_samples, windows)))
    position = {number: 0 for number in gaps_by_stretch}
    compared_keys: set[tuple[int, int]] = set()
    for number, window, replay_row, watch in compared:
        gap = float(gaps_by_stretch[number][position[number]])
        position[number] += 1
        compared_keys.add((number, window))
        if window == 0:
            continue
        match = match_window(replay_row, watch, gap)
        result.compared += 1
        result.first_window = window if result.first_window is None else min(result.first_window, window)
        result.last_window = window if result.last_window is None else max(result.last_window, window)
        result.prob_diff = max(result.prob_diff, match.prob_diff)
        result.below_diff = max(result.below_diff, match.below_diff)
        if boot.w_text[(number, window)] != repr(float(replay_row["pred_tremor_proba"])):
            result.text_differs += 1
        if not match.passed:
            result.problems.append(
                f"boot {boot.boot_id} stretch {number} window {window}: the {match.failed} differs"
            )
        if match.code_differs or match.peak_differs or not match.passed:
            result.differs.append(Differ(boot.boot_id, number, window, replay_row, dict(watch), match))

    for number, part in sorted(parts.items()):
        if number not in matched or part.rate_uhz == 0:
            continue
        readings = range(part.first, part.last + 1)
        counts = np.array([boot.counts[n] for n in readings], dtype=np.int64)
        toolbox = toolbox_windows(counts, part.rate_uhz)
        for row in toolbox.itertuples(index=False):
            k = int(row.k)
            if k < 1 or (number, TOOLBOX_EVERY * k) not in compared_keys:
                continue
            watch = boot.w_lines[(number, TOOLBOX_EVERY * k)]
            result.toolbox_compared += 1
            result.toolbox_prob_diff = max(result.toolbox_prob_diff,
                                           abs(float(row.pred_tremor_proba) - watch["pred_tremor_proba"]))
            result.watch_codes.append(int(watch["code"]))
            result.toolbox_codes.append(int(row.code))
            if int(row.code) == int(watch["code"]):
                result.toolbox_agree += 1
            else:
                near = (abs(float(row.pred_tremor_proba) - CUT_OFF) <= PROB_NEAR
                        or abs(float(row.below_tremor_power) - MOVEMENT_THRESHOLD) <= BELOW_NEAR
                        or float(row.peak_gap) < GAP_NEAR)
                result.toolbox_differs.append(
                    ToolboxDiffer(boot.boot_id, number, k, int(row.code), int(watch["code"]), near)
                )


def compare(lines: list[str], replay: Path, cut_short: bool = False) -> Result:
    """Run replay and the toolbox on the recording's lines and compare both with the watch."""
    with tempfile.TemporaryDirectory() as folder:
        samples_path = Path(folder) / "samples.csv"
        rows, stderr = run_replay(replay, lines, samples_path)
        samples = pd.read_csv(samples_path, float_precision="round_trip")
    result = Result(summary=stderr.strip(), cut_short=cut_short)
    boots = watch_side(lines)
    if not boots:
        raise StopRun("the recording holds no B line")
    for boot in boots:
        result.boots.append(boot.boot_id)
        boot_rows = rows[rows["boot"] == boot.boot_id]
        last = int(boot_rows["window"].iloc[-1]) if len(boot_rows) else None
        compare_boot(result, boot, rows, samples, last)
    if result.compared == 0:
        result.problems.append("no window was checked")
    return result


def percent(value: float | None) -> str:
    return "none" if value is None else f"{value:.1f} percent"


def report_lines(recording: Path, result: Result) -> list[str]:
    """Give the report as Markdown lines."""
    passed = not result.problems
    agree = 100.0 * result.toolbox_agree / result.toolbox_compared if result.toolbox_compared else None
    span = (f", from window {result.first_window} to window {result.last_window}"
            if result.first_window is not None else "")
    lines = [
        f"# Session comparison of {recording.name}",
        "",
        f"- The recording is {recording}.",
        f"- The toolbox is ParaDigMa {importlib.metadata.version('paradigma')}.",
        f"- The boots are {', '.join(str(b) for b in result.boots)}.",
        f"- replay wrote: {result.summary}",
        f"- The result is {'pass' if passed else 'fail'}.",
        *(["- The gzip file was cut short, so the comparison used the whole lines before the cut."]
          if result.cut_short else []),
        "",
        "## Stretches",
        "",
        "| Boot | Stretch | First reading | t0 (us) | Watch rate (uHz) | Replay rate (uHz) | Checked |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for s in result.stretches:
        lines.append(f"| {s.boot_id} | {s.stretch} | {s.first} | {s.t0_us} "
                     f"| {s.watch_rate if s.watch_rate is not None else 'none'} "
                     f"| {s.replay_rate if s.replay_rate is not None else 'none'} | {s.checked} |")
    lines += [
        "",
        "## Replay and the watch",
        "",
        f"- The run compared {result.compared} windows{span}. Window 0 of each stretch is left out.",
        f"- {len(result.differs)} windows differ in the code, the peak, or the probability.",
        f"- The largest difference in the probability is {result.prob_diff:.3g}, and the limit is {PROB_LIMIT:g}.",
        f"- The largest difference in the low-frequency sum, as a share of replay's sum, is "
        f"{result.below_diff:.3g}, and the limit is {BELOW_LIMIT:g}.",
        f"- The probability's text differs from replay's shortest text on {result.text_differs} windows.",
        f"- {result.not_checked[REASON_GAP]} windows were not checked because they lie {REASON_GAP}.",
        f"- {result.not_checked[REASON_START]} windows were not checked because they lie {REASON_START}.",
        f"- {result.exempt_last} replay windows at the end of a boot have no W line, which is allowed.",
        f"- replay gave {result.replay_only} windows in stretches that it starts after a gap with no S line, "
        "and they are not compared.",
        f"- {len(result.problems)} checks failed.",
        "",
    ]
    if result.differs:
        lines += ["| Boot | Stretch | Window | Replay code, probability, peak | Watch code, probability, peak "
                  "| Near a cut-off | Passed |", "| --- | ---: | ---: | --- | --- | --- | --- |"]
        for d in result.differs:
            lines.append(
                f"| {d.boot_id} | {d.stretch} | {d.window} "
                f"| {int(d.replay['code'])}, {d.replay['pred_tremor_proba']!r}, {d.replay['freq_peak']} "
                f"| {int(d.watch['code'])}, {d.watch['pred_tremor_proba']!r}, {d.watch['freq_peak']} "
                f"| {'yes' if d.match.near_cut_off else 'no'} | {'yes' if d.match.passed else 'no'} |"
            )
    else:
        lines.append("No window differs.")
    if result.problems:
        lines += ["", "### Failed checks", ""] + [f"- {p}" for p in result.problems]
    lines += [
        "",
        "## The toolbox and the watch",
        "",
        f"- The toolbox's window k was compared with the watch's window 4k from k = 1 on. "
        f"The toolbox's codes agree on {result.toolbox_agree} of {result.toolbox_compared} windows, "
        f"which is {percent(agree)}.",
        f"- The largest difference in the probability is {result.toolbox_prob_diff:.3g}.",
        "- The toolbox's agreement has no pass limit.",
        "",
    ]
    if result.toolbox_differs:
        lines += ["| Boot | Stretch | k | Toolbox code | Watch code | Toolbox near a cut-off |",
                  "| --- | ---: | ---: | ---: | ---: | --- |"]
        for t in result.toolbox_differs:
            lines.append(f"| {t.boot_id} | {t.stretch} | {t.k} | {t.toolbox_code} | {t.watch_code} "
                         f"| {'yes' if t.near_cut_off else 'no'} |")
    else:
        lines.append("No window differs.")
    lines += [
        "",
        "## Share",
        "",
        f"- Over the {result.toolbox_compared} windows that the toolbox compares, the share of still time with "
        f"tremor is {percent(share_of(result.watch_codes))} from the watch's codes and "
        f"{percent(share_of(result.toolbox_codes))} from the toolbox's codes.",
        "- The share has no pass limit.",
    ]
    return lines


def default_report(recording: Path) -> Path:
    """Give the recording's path with its suffixes replaced by _session.md."""
    suffixes = "".join(recording.suffixes)
    stem = recording.name[: len(recording.name) - len(suffixes)] if suffixes else recording.name
    return recording.with_name(f"{stem}_session.md")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare a recording with replay and the toolbox.")
    parser.add_argument("recording", type=Path, help="a recording from the watch, as gzip or plain text")
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY, help="the replay program")
    parser.add_argument("--report", type=Path, default=None, help="the report to write")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the comparison, write the report, and give the exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    report = args.report if args.report is not None else default_report(args.recording)
    lines, cut_short = read_recording(args.recording)
    if cut_short:
        logger.warning("%s was cut short. The comparison uses the %d whole lines before the cut.",
                       args.recording, len(lines))
    try:
        result = compare(lines, args.replay, cut_short)
    except StopRun as stop:
        logger.error("%s", stop)
        return 1
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(report_lines(args.recording, result)) + "\n", encoding="utf-8")
    logger.info("Compared %d windows with replay. Largest probability difference %.3g.",
                result.compared, result.prob_diff)
    logger.info("The toolbox agrees on %d of %d windows.", result.toolbox_agree, result.toolbox_compared)
    logger.info("%d windows not checked after a gap, %d before the recording.",
                result.not_checked[REASON_GAP], result.not_checked[REASON_START])
    for problem in result.problems:
        logger.error("%s", problem)
    logger.info("The result is %s. The report is %s.", "pass" if not result.problems else "fail", report)
    return 0 if not result.problems else 1


if __name__ == "__main__":
    sys.exit(main())
