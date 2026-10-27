"""Make the saved test windows for the C detector and the toolbox's answers for them.

Run it from the repo root in the reference venv. Fixed seeds make every run write the same files.

    reference/.venv/bin/python tests/detector/make_windows.py

windows.csv has one row per reading and answers.csv one row per window. Every
reading is a 32-bit float, and the toolbox gets the same values as 64-bit
floats, so both sides see the same input.

There are 322 windows. 200 come from the five kinds in reference/compare.py.
120 sit near a cut-off, each tuned by bisection on one amplitude. 20 test the
ends of the peak band, one is all zeros, and one is a clipped 5 Hz shake. The
answers come from one toolbox run on all 322 windows as one recording, as
compare.py does. The script writes nothing if a tuned window leaves its band in
that run or the welch peak differs from freq_peak.
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
import paradigma
from paradigma.classification import ClassifierPackage
from paradigma.config import TremorConfig
from paradigma.pipelines.tremor_pipeline import detect_tremor, extract_tremor_features
from scipy import signal

logger = logging.getLogger("make_windows")

DEFAULT_OUT = Path(__file__).resolve().parent
MODEL_FILE = Path(paradigma.__file__).resolve().parent / "assets" / "tremor_detection_clf_package.pkl"

FS = 100
N = 400
AXES = ["gyroscope_x", "gyroscope_y", "gyroscope_z"]
T = np.arange(N) / FS

# The fine spectrum's settings, as extract_spectral_domain_features derives them from TremorConfig.
PSD_SEG = 300
PSD_OVERLAP = int(PSD_SEG * 0.8)
PSD_NFFT = 400
PSD_FREQS = np.arange(PSD_NFFT // 2 + 1) * FS / PSD_NFFT
PEAK_STEPS = slice(4, 101)  # 1 to 25 Hz, both ends included

MOVEMENT_THRESHOLD = 50.0
CUT_OFF = float(ClassifierPackage.load(MODEL_FILE).threshold)
# A window is near a cut-off when one of these holds.
PROB_NEAR = 0.0001
BELOW_NEAR = 0.005
GAP_NEAR = 0.0001
REST_TREMOR_HZ = (3.0, 7.0)
MAX_STEPS = 200
MAX_DRAWS = 50

MFCC_COLUMNS = [f"mfcc_{i}" for i in range(1, 13)]
ANSWER_COLUMNS = [
    "window", "group", *MFCC_COLUMNS, "pred_tremor_proba", "below_tremor_power", "freq_peak",
    "pred_arm_at_rest", "pred_tremor_checked", "peak_gap",
]


def fail(message: str) -> NoReturn:
    """Log the reason and stop the run with exit code 1."""
    logger.error(message)
    sys.exit(1)


def rounded(window: np.ndarray) -> np.ndarray:
    """Round a window to 32-bit floats, which is what both sides see."""
    return np.asarray(window, dtype=np.float64).astype(np.float32)


def toolbox(windows: np.ndarray) -> pd.DataFrame:
    """Run the toolbox on float32 windows of shape (n, 400, 3) as one recording at 100 Hz."""
    data = windows.reshape(-1, 3).astype(np.float64)
    config = TremorConfig()
    frame = pd.DataFrame(data, columns=AXES)
    frame.insert(0, "time", np.arange(len(frame)) / FS)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = detect_tremor(extract_tremor_features(frame, config), config, MODEL_FILE)
    return out.reset_index(drop=True)


def fine_spectrum(windows: np.ndarray) -> np.ndarray:
    """Return the toolbox's fine spectrum with the three axes added, shape (n, 201).

    It calls scipy welch with the same arguments as the toolbox's
    extract_spectral_domain_features, then adds the axes as compute_total_power does.
    """
    window = signal.get_window("hann", PSD_SEG, fftbins=False)
    _, psd = signal.welch(
        x=np.asarray(windows, dtype=np.float64), fs=FS, window=window, nperseg=PSD_SEG,
        noverlap=PSD_OVERLAP, nfft=PSD_NFFT, detrend=False, scaling="density", axis=1,
    )
    return np.sum(psd, axis=-1)


def peak_gaps(total_psd: np.ndarray) -> np.ndarray:
    """Return the largest minus the second largest step from 1 to 25 Hz, divided by the largest.

    A spectrum whose largest step is 0 has a gap of 0, because every step ties.
    """
    top = np.sort(total_psd[:, PEAK_STEPS], axis=1)
    largest, second = top[:, -1], top[:, -2]
    return np.divide(largest - second, largest, out=np.zeros_like(largest), where=largest > 0)


@dataclass(frozen=True)
class Target:
    """A band of distances from a cut-off, on one side of it."""

    cut: float
    near: float
    far: float
    side: int


def distance(target: Target, value: float) -> float:
    """Return how far the value lies from the cut-off on the target's side."""
    return (value - target.cut) * target.side


def in_band(target: Target, value: float) -> bool:
    return target.near <= distance(target, value) <= target.far


def in_inner_band(target: Target, value: float) -> bool:
    """Return True when the value lies in the middle 80 percent of the band."""
    margin = 0.1 * (target.far - target.near)
    return target.near + margin <= distance(target, value) <= target.far - margin


def aim_for(target: Target, rng: np.random.Generator) -> float:
    """Return a seeded value in the middle 60 percent of the band."""
    margin = 0.2 * (target.far - target.near)
    return target.cut + target.side * float(rng.uniform(target.near + margin, target.far - margin))


@dataclass(frozen=True)
class Spec:
    """What one saved window must show in the toolbox's answers."""

    group: str
    metric: str | None = None
    target: Target | None = None
    model_yes: bool = False
    at_rest: bool = False
    peak_low: float | None = None
    peak_high: float | None = None


@dataclass(frozen=True)
class Reading:
    """The toolbox's numbers for one window, with the signed gap between two chosen peak steps."""

    prob: float
    below: float
    peak: float
    model_yes: bool
    at_rest: bool
    gap: float
    signed_gap: float


def read_one(window: np.ndarray, steps: tuple[int, int] | None = None) -> Reading:
    """Run the toolbox and the welch copy on one rounded window."""
    row = toolbox(window[np.newaxis]).iloc[0]
    total = fine_spectrum(window[np.newaxis])
    signed = 0.0
    if steps is not None:
        inside, outside = total[0, steps[0]], total[0, steps[1]]
        signed = float((outside - inside) / max(inside, outside))
    return Reading(
        prob=float(row["pred_tremor_proba"]), below=float(row["below_tremor_power"]),
        peak=float(row["freq_peak"]), model_yes=bool(row["pred_tremor_logreg"]),
        at_rest=bool(row["pred_arm_at_rest"]), gap=float(peak_gaps(total)[0]), signed_gap=signed,
    )


def near(reading: Reading) -> dict[str, bool]:
    """Return which cut-offs the reading lies near."""
    return {
        "prob": abs(reading.prob - CUT_OFF) <= PROB_NEAR,
        "below": abs(reading.below - MOVEMENT_THRESHOLD) <= BELOW_NEAR,
        "gap": reading.gap < GAP_NEAR,
    }


def meets(reading: Reading, spec: Spec) -> bool:
    """Return True when the reading meets the spec's conditions other than its target band.

    A window with conditions must also lie clear of every cut-off except the
    one its group targets, so that only that cut-off decides its answer.
    """
    if spec.model_yes and not reading.model_yes:
        return False
    if spec.at_rest and not reading.at_rest:
        return False
    if spec.peak_low is not None and reading.peak < spec.peak_low:
        return False
    if spec.peak_high is not None and reading.peak > spec.peak_high:
        return False
    if spec.model_yes or spec.at_rest or spec.peak_low is not None:
        return not any(found for metric, found in near(reading).items() if metric != spec.metric)
    return True


def bisect(
    make: Callable[[float], np.ndarray], measure: Callable[[np.ndarray], float], target: Target,
    span: tuple[float, float], rng: np.random.Generator,
) -> np.ndarray | None:
    """Tune one amplitude until the measured value lies in the target band.

    The measured value must grow with the amplitude. Return None when the span
    does not cross the aim or the steps run out.
    """
    aim = aim_for(target, rng)
    lo, hi = span
    if not measure(make(lo)) < aim < measure(make(hi)):
        return None
    for _ in range(MAX_STEPS):
        mid = 0.5 * (lo + hi)
        window = make(mid)
        value = measure(window)
        if in_inner_band(target, value):
            return window
        if value < aim:
            lo = mid
        else:
            hi = mid
    return None


def direction(rng: np.random.Generator) -> np.ndarray:
    """Return a seeded share of a movement over the three axes."""
    return rng.uniform(0.2, 1.0, 3) * rng.choice([-1.0, 1.0], 3)


def sine(freq: float, amp: float, axes: np.ndarray, phase: float) -> np.ndarray:
    """Return a sine of one frequency over the three axes, shape (400, 3)."""
    return np.outer(np.sin(2 * np.pi * freq * T + phase), axes * amp)


def compare_windows() -> tuple[list[np.ndarray], list[Spec]]:
    """Make the 200 windows of reference/compare.py with a copy of its generator and seed 1."""
    rng = np.random.default_rng(1)
    t = T

    def make(kind: str) -> np.ndarray:
        noise = rng.normal(0, 1.5, (N, 3))
        if kind == "rest":
            return noise
        if kind == "tremor":
            f = rng.uniform(4, 6); a = rng.uniform(20, 80, 3)  # noqa: E702
            return noise + np.outer(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)), a) * rng.choice([-1, 1], 3)
        if kind == "small_tremor":
            f = rng.uniform(4, 6); a = rng.uniform(3, 8, 3)  # noqa: E702
            return noise + np.outer(np.sin(2 * np.pi * f * t), a)
        if kind == "walk":
            f = rng.uniform(0.8, 2.0); a = rng.uniform(40, 150, 3)  # noqa: E702
            return noise + np.outer(np.sin(2 * np.pi * f * t + 1), a)
        if kind == "walk_plus_tremor":
            return make("walk") + make("tremor")
        raise ValueError(kind)

    windows: list[np.ndarray] = []
    specs: list[Spec] = []
    for kind in ["rest", "tremor", "small_tremor", "walk", "walk_plus_tremor"]:
        for _ in range(40):
            windows.append(rounded(make(kind)))
            specs.append(Spec(kind))
    return windows, specs


def tune_group(
    rng: np.random.Generator, spec: Spec, draw: Callable[[], tuple[Callable[[float], np.ndarray], tuple[float, float]]],
    measure: Callable[[np.ndarray], float],
) -> np.ndarray:
    """Draw seeded windows until one tunes into the spec's band and meets its conditions."""
    assert spec.target is not None
    for _ in range(MAX_DRAWS):
        make, span = draw()
        window = bisect(make, measure, spec.target, span, rng)
        if window is not None and meets(read_one(window), spec):
            return window
    fail(f"no window in group {spec.group} reached its target band")


def bands(cut: float, near: tuple[float, float], wide: tuple[float, float], n_near: int, n_wide: int,
          name: str) -> list[tuple[str, Target]]:
    """Return the targets of one near-cut-off group: tight ones on both sides, then wide ones above and below."""
    out = [(f"{name}_tight", Target(cut, near[0], near[1], 1 if i % 2 == 0 else -1)) for i in range(n_near)]
    out += [(f"{name}_above", Target(cut, wide[0], wide[1], 1)) for _ in range(n_wide)]
    out += [(f"{name}_below", Target(cut, wide[0], wide[1], -1)) for _ in range(n_wide)]
    return out


def prob_windows() -> tuple[list[np.ndarray], list[Spec]]:
    """Make 40 windows whose probability sits near the cut-off, with the peak in 3 to 7 Hz and the arm at rest."""
    rng = np.random.default_rng(2)
    windows: list[np.ndarray] = []
    specs: list[Spec] = []
    for group, target in bands(CUT_OFF, (1e-6, 5e-5), (2e-4, 1e-3), 10, 15, "near_prob"):
        spec = Spec(group, "prob", target, at_rest=True, peak_low=REST_TREMOR_HZ[0], peak_high=REST_TREMOR_HZ[1])

        def draw() -> tuple[Callable[[float], np.ndarray], tuple[float, float]]:
            noise = rng.normal(0, 1.5, (N, 3))
            freq, axes, phase = rng.uniform(4, 6), direction(rng), rng.uniform(0, 2 * np.pi)
            return (lambda amp: rounded(noise + sine(freq, amp, axes, phase))), (0.0, 20.0)

        windows.append(tune_group(rng, spec, draw, lambda w: read_one(w).prob))
        specs.append(spec)
    return windows, specs


def below_windows() -> tuple[list[np.ndarray], list[Spec]]:
    """Make 40 windows whose low-frequency sum sits near 50, with the model saying yes and the peak in 3 to 7 Hz."""
    rng = np.random.default_rng(3)
    windows: list[np.ndarray] = []
    specs: list[Spec] = []
    for group, target in bands(MOVEMENT_THRESHOLD, (1e-4, 2.5e-3), (0.01, 0.05), 10, 15, "near_below"):
        spec = Spec(group, "below", target, model_yes=True, peak_low=REST_TREMOR_HZ[0],
                    peak_high=REST_TREMOR_HZ[1])

        def draw() -> tuple[Callable[[float], np.ndarray], tuple[float, float]]:
            noise = rng.normal(0, 1.5, (N, 3))
            shake = sine(rng.uniform(4.5, 5.5), rng.uniform(15, 30), direction(rng), rng.uniform(0, 2 * np.pi))
            freq, axes, phase = rng.uniform(1.0, 2.0), direction(rng), rng.uniform(0, 2 * np.pi)
            return (lambda amp: rounded(noise + shake + sine(freq, amp, axes, phase))), (0.0, 60.0)

        windows.append(tune_group(rng, spec, draw, lambda w: read_one(w).below))
        specs.append(spec)
    return windows, specs


def tie_windows() -> tuple[list[np.ndarray], list[Spec]]:
    """Make 20 windows with two peaks of almost equal height, one inside 3 to 7 Hz and one outside."""
    rng = np.random.default_rng(4)
    windows: list[np.ndarray] = []
    specs: list[Spec] = []
    groups = [("peak_tie_tight", 1e-6, 5e-5)] * 10 + [("peak_tie_wide", 2e-4, 1e-3)] * 10
    for i, (group, near, far) in enumerate(groups):
        # The inside peak is larger in even windows and the outside peak in odd ones.
        target = Target(0.0, near, far, -1 if i % 2 == 0 else 1)
        f_in = float(rng.choice([4.5, 5.0, 5.5]))
        f_out = float(rng.choice([8.0, 8.5, 9.0]))
        steps = (int(f_in * 4), int(f_out * 4))
        peak = f_in if target.side < 0 else f_out
        spec = Spec(group, "gap", Target(0.0, near, far, 1), model_yes=True, at_rest=True, peak_low=peak,
                    peak_high=peak)

        def draw() -> tuple[Callable[[float], np.ndarray], tuple[float, float]]:
            noise = rng.normal(0, 1.5, (N, 3))
            amp_in = rng.uniform(8, 15)
            inside = sine(f_in, amp_in, direction(rng), rng.uniform(0, 2 * np.pi))
            axes, phase = direction(rng), rng.uniform(0, 2 * np.pi)
            return (lambda amp: rounded(noise + inside + sine(f_out, amp, axes, phase))), (0.0, 4 * amp_in)

        def measure(window: np.ndarray) -> float:
            reading = read_one(window, steps)
            return reading.signed_gap if np.isclose(reading.gap, abs(reading.signed_gap), rtol=0, atol=1e-12) \
                else np.sign(reading.signed_gap) * np.inf

        for _ in range(MAX_DRAWS):
            make, span = draw()
            window = bisect(make, measure, target, span, rng)
            if window is not None and meets(read_one(window), spec):
                break
        else:
            fail(f"no window in group {group} reached its target band")
        windows.append(window)
        specs.append(spec)
    return windows, specs


def band_end_windows() -> tuple[list[np.ndarray], list[Spec]]:
    """Make 20 windows whose peak sits at 3.0, 7.0, 7.25, and 2.75 Hz, five each.

    A second, smaller sine near 5 Hz makes the model say yes. The first three
    groups also need the arm at rest. These windows are not tuned.
    """
    rng = np.random.default_rng(5)
    cases = [
        (3.0, (10.0, 14.0), True), (7.0, (6.0, 14.0), True), (7.25, (6.0, 14.0), True), (2.75, (35.0, 60.0), False),
    ]
    windows: list[np.ndarray] = []
    specs: list[Spec] = []
    for freq, amps, rest in cases:
        spec = Spec(f"peak_{freq}", model_yes=True, at_rest=rest, peak_low=freq, peak_high=freq)
        for _ in range(5):
            for _ in range(MAX_DRAWS):
                amp, ratio = rng.uniform(*amps), rng.uniform(0.85, 0.97)
                axes = direction(rng)
                window = rounded(
                    rng.normal(0, 1.5, (N, 3)) + sine(freq, amp, axes, rng.uniform(0, 2 * np.pi))
                    + sine(float(rng.choice([4.5, 5.0])), amp * ratio, axes, rng.uniform(0, 2 * np.pi))
                )
                if meets(read_one(window), spec):
                    break
            else:
                fail(f"no window in group {spec.group} met its conditions")
            windows.append(window)
            specs.append(spec)
    return windows, specs


def edge_windows() -> tuple[list[np.ndarray], list[Spec]]:
    """Make a window of zeros and a 5 Hz shake of 1500 deg/s clipped at 1024, as in reference/latency_test.py."""
    rng = np.random.default_rng(6)
    shake = np.outer(np.sin(2 * np.pi * 5.0 * T), np.array([1.0, 0.35, 0.2]) * 1500.0) + rng.normal(0, 1.0, (N, 3))
    return [rounded(np.zeros((N, 3))), rounded(np.clip(shake, -1024, 1024))], [Spec("zeros"), Spec("clipped")]


def check_run(out: pd.DataFrame, gaps: np.ndarray, total: np.ndarray, specs: Sequence[Spec]) -> None:
    """Stop the run if a window misses its band or its conditions in the batch run, or a welch peak differs."""
    if len(out) != len(specs):
        fail(f"the toolbox gave {len(out)} windows, not {len(specs)}")
    welch_peak = PSD_FREQS[PEAK_STEPS][np.argmax(total[:, PEAK_STEPS], axis=1)]
    for i, spec in enumerate(specs):
        row = out.iloc[i]
        if welch_peak[i] != row["freq_peak"]:
            fail(f"window {i}: the welch peak {welch_peak[i]} is not freq_peak {row['freq_peak']}")
        reading = Reading(
            prob=float(row["pred_tremor_proba"]), below=float(row["below_tremor_power"]), peak=float(row["freq_peak"]),
            model_yes=bool(row["pred_tremor_logreg"]), at_rest=bool(row["pred_arm_at_rest"]), gap=float(gaps[i]),
            signed_gap=0.0,
        )
        if not meets(reading, spec):
            fail(f"window {i} in group {spec.group} misses its conditions in the batch run")
        if spec.target is not None:
            value = {"prob": reading.prob, "below": reading.below, "gap": reading.gap}[str(spec.metric)]
            if not in_band(spec.target, value):
                fail(f"window {i} in group {spec.group} has {spec.metric} {value!r}, outside its band")


def number(value: float) -> str:
    """Return the shortest text that gives back the same 64-bit value."""
    return repr(float(value))


def write_files(windows: np.ndarray, out: pd.DataFrame, gaps: np.ndarray, specs: Sequence[Spec], folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    readings = ["gyroscope_x,gyroscope_y,gyroscope_z"]
    readings += [",".join(str(v) for v in row) for row in windows.reshape(-1, 3)]
    (folder / "windows.csv").write_text("\n".join(readings) + "\n", encoding="ascii")

    lines = [",".join(ANSWER_COLUMNS)]
    for i, spec in enumerate(specs):
        row = out.iloc[i]
        values = [str(i), spec.group, *(number(row[c]) for c in MFCC_COLUMNS)]
        values += [number(row["pred_tremor_proba"]), number(row["below_tremor_power"]), number(row["freq_peak"])]
        values += [str(int(row["pred_arm_at_rest"])), str(int(row["pred_tremor_checked"])), number(gaps[i])]
        lines.append(",".join(values))
    (folder / "answers.csv").write_text("\n".join(lines) + "\n", encoding="ascii")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Make the saved test windows for the C detector.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="the folder for windows.csv and answers.csv")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)

    windows: list[np.ndarray] = []
    specs: list[Spec] = []
    for make in (compare_windows, prob_windows, below_windows, tie_windows,
                 band_end_windows, edge_windows):
        found, found_specs = make()
        windows += found
        specs += found_specs
        logger.info("made %d windows", len(windows))

    stack = np.stack(windows).astype(np.float32)
    out = toolbox(stack)
    total = fine_spectrum(stack)
    gaps = peak_gaps(total)
    check_run(out, gaps, total, specs)
    write_files(stack, out, gaps, specs, args.out)
    logger.info("wrote %d windows to %s", len(specs), args.out)


if __name__ == "__main__":
    main()
