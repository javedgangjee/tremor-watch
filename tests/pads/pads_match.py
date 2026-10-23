"""Check that the C detector agrees with the toolbox on every PADS recording.

The script runs in the reference venv, because it needs the toolbox, and it needs
the laptop build of replay. Run it from the repo root after the C build.

    reference/.venv/bin/python tests/pads/pads_match.py

For each recording it runs the toolbox in the way reference/pads_counts.py does and
keeps the 12 numbers. It checks that this run gives the same answers as the
committed reference/results/pads_windows.csv. It then runs replay on the file and
compares replay window 4k with the toolbox's window k under the rule in
match_window(). It compares the C counts with reference/results/pads_counts.csv
and writes the match report. It exits with code 0 only when every check passes.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.metadata
import io
import logging
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import NoReturn

import numpy as np
import pandas as pd
from paradigma.classification import ClassifierPackage
from paradigma.config import TremorConfig
from paradigma.pipelines.tremor_pipeline import detect_tremor, extract_tremor_features

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "reference"))
sys.path.insert(0, str(REPO / "tests" / "detector"))
from make_windows import PEAK_STEPS, PSD_FREQS, fine_spectrum, peak_gaps  # noqa: E402
from pads_counts import (  # noqa: E402
    MODEL_FILE,
    TASKS,
    WRISTS,
    count_windows,
    cut_start,
    load_groups,
    read_gyroscope,
)

logger = logging.getLogger("pads_match")

KISS_FFT = "tag 131.2.0, commit 7bce4153c6bc8aba2db0e889e576f9d00505cbe1"
TABLES = REPO / "core" / "detector_tables.h"
RESULTS = REPO / "reference" / "results"
FS = 100
WINDOW_ROWS = 400
REPLAY_EVERY = 4  # the toolbox cuts a window every 4 s, and replay every 1 s

LIMIT = 0.0001  # the limit for the 12 numbers and the probability, from Build order step 5
PROB_NEAR = 0.0001
BELOW_NEAR = 0.005
GAP_NEAR = 0.0001
MOVEMENT_THRESHOLD = 50.0
CUT_OFF = float(ClassifierPackage.load(MODEL_FILE).threshold)

MFCC_COLUMNS = [f"mfcc_{i}" for i in range(1, 13)]
ANSWER_COLUMNS = ["pred_tremor_proba", "below_tremor_power", "freq_peak", "pred_arm_at_rest", "pred_tremor_checked"]
WINDOW_KEYS = ["subject", "group", "task", "wrist", "window"]


def fail(message: str) -> NoReturn:
    """Log the reason and stop the run with exit code 1."""
    logger.error(message)
    sys.exit(1)


@dataclass(frozen=True)
class Match:
    """The result of comparing one C window with the toolbox's window."""

    passed: bool
    mfcc_diff: float
    prob_diff: float
    below_rel: float
    answer_differs: bool
    peak_differs: bool
    near_cut_off: bool
    near_tie: bool


def match_window(toolbox: Mapping[str, float], c: Mapping[str, float]) -> Match:
    """Apply the match rule of requirements 9, 27, and 29 to one window.

    The 12 numbers and the probability must agree within 0.0001. The tremor and
    arm at rest answers must agree unless the toolbox's window is near a cut-off.
    The peak must agree unless the toolbox's two largest peak steps nearly tie.
    """
    mfcc_diff = max(abs(float(c[name]) - float(toolbox[name])) for name in MFCC_COLUMNS)
    prob_diff = abs(float(c["pred_tremor_proba"]) - float(toolbox["pred_tremor_proba"]))
    below = float(toolbox["below_tremor_power"])
    below_rel = abs(float(c["below_tremor_power"]) - below) / abs(below) if below != 0 else 0.0
    near_tie = float(toolbox["peak_gap"]) < GAP_NEAR
    near_cut_off = (
        abs(float(toolbox["pred_tremor_proba"]) - CUT_OFF) <= PROB_NEAR
        or abs(below - MOVEMENT_THRESHOLD) <= BELOW_NEAR
        or near_tie
    )
    answer_differs = any(int(c[name]) != int(toolbox[name]) for name in ["pred_tremor_checked", "pred_arm_at_rest"])
    peak_differs = float(c["freq_peak"]) != float(toolbox["freq_peak"])
    passed = (
        mfcc_diff <= LIMIT
        and prob_diff <= LIMIT
        and (near_cut_off or not answer_differs)
        and (near_tie or not peak_differs)
    )
    return Match(passed, mfcc_diff, prob_diff, below_rel, answer_differs, peak_differs, near_cut_off, near_tie)


def toolbox_rows(gyro: np.ndarray) -> pd.DataFrame:
    """Run the toolbox on one recording at 100 Hz as reference/pads_counts.py does.

    Return one row per 4 second window with the 12 numbers, the answers, and the
    peak gap of requirement 27.
    """
    columns = ["window", *MFCC_COLUMNS, *ANSWER_COLUMNS, "peak_gap"]
    if len(gyro) < WINDOW_ROWS:
        return pd.DataFrame(columns=columns)
    config = TremorConfig()
    frame = pd.DataFrame(gyro, columns=config.gyroscope_colnames)
    frame.insert(0, config.time_colname, np.arange(len(gyro)) / FS)
    out = detect_tremor(extract_tremor_features(frame, config), config, MODEL_FILE).reset_index(drop=True)

    n = len(out)
    windows = gyro[: n * WINDOW_ROWS].reshape(n, WINDOW_ROWS, 3)
    total = fine_spectrum(windows.astype(np.float64))
    welch_peak = PSD_FREQS[PEAK_STEPS][np.argmax(total[:, PEAK_STEPS], axis=1)]
    if not np.array_equal(welch_peak, out["freq_peak"].to_numpy(dtype=float)):
        fail("the welch peak differs from the toolbox's freq_peak")
    out["peak_gap"] = peak_gaps(total)
    out.insert(0, "window", np.arange(n))
    return out[columns]


def replay_rows(replay: Path, path: Path) -> pd.DataFrame:
    """Run replay on one PADS file and return its rows."""
    ran = subprocess.run([str(replay), "--pads", str(path)], capture_output=True, text=True, check=True)
    return pd.read_csv(io.StringIO(ran.stdout), float_precision="round_trip")


@dataclass(frozen=True)
class Differ:
    """One window where an answer or the peak differs, or the match rule fails."""

    keys: dict[str, str]
    window: int
    toolbox: pd.Series
    c: pd.Series
    match: Match


@dataclass
class Run:
    """Everything the report needs from the run."""

    n_files: int = 0
    n_missing: int = 0
    n_windows: int = 0
    n_extra: int = 0
    n_failed: int = 0
    mfcc_diff: float = 0.0
    prob_diff: float = 0.0
    below_rel: float = 0.0
    n_near: int = 0
    differs: list[Differ] = field(default_factory=list)
    c_windows: list[pd.DataFrame] = field(default_factory=list)


def check_toolbox(rows: pd.DataFrame, committed: pd.DataFrame, name: str) -> None:
    """Stop the run if the toolbox's answers differ from the committed pads_windows.csv."""
    if len(rows) != len(committed):
        fail(f"{name}: the toolbox gave {len(rows)} windows, and pads_windows.csv holds {len(committed)}")
    for column in ANSWER_COLUMNS:
        ours = rows[column].to_numpy(dtype=float)
        theirs = committed[column].to_numpy(dtype=float)
        if not np.array_equal(ours, theirs):
            fail(f"{name}: the toolbox's {column} differs from pads_windows.csv")


def compare_file(run: Run, replay: Path, path: Path, keys: dict[str, str], committed: pd.DataFrame) -> None:
    """Compare the C detector with the toolbox on one recording and add the result to the run."""
    tb = toolbox_rows(cut_start(read_gyroscope(path)))
    check_toolbox(tb, committed, path.name)
    c_all = replay_rows(replay, path)
    c = c_all[c_all["window"] % REPLAY_EVERY == 0].copy()
    c["window"] = c["window"] // REPLAY_EVERY
    c = c.reset_index(drop=True)
    if len(c) != len(tb):
        run.n_extra += abs(len(c) - len(tb))
        run.n_failed += 1
        logger.error("%s: replay gave %d windows on the 4 s grid, and the toolbox %d", path.name, len(c), len(tb))
    for k in range(min(len(c), len(tb))):
        match = match_window(tb.iloc[k], c.iloc[k])
        run.n_windows += 1
        run.mfcc_diff = max(run.mfcc_diff, match.mfcc_diff)
        run.prob_diff = max(run.prob_diff, match.prob_diff)
        run.below_rel = max(run.below_rel, match.below_rel)
        run.n_near += int(match.near_cut_off)
        if not match.passed:
            run.n_failed += 1
        if match.answer_differs or match.peak_differs or not match.passed:
            run.differs.append(Differ(keys, k, tb.iloc[k], c.iloc[k], match))
    c_rows = c[["window", "pred_tremor_checked"]].copy()
    for name, value in keys.items():
        c_rows.insert(0, name, value)
    run.c_windows.append(c_rows)


def run_match(data: Path, replay: Path) -> Run:
    """Compare every expected PADS recording."""
    groups = load_groups(data / "preprocessed" / "file_list.csv")
    series = data / "movement" / "timeseries"
    committed = pd.read_csv(RESULTS / "pads_windows.csv", dtype={"subject": str}, float_precision="round_trip")
    by_file = {key: part.reset_index(drop=True) for key, part in committed.groupby(["subject", "task", "wrist"])}
    empty = committed.iloc[0:0]
    run = Run()
    expected = [(s, t, w) for s in groups for t in TASKS for w in WRISTS]
    for i, (subject, task, wrist) in enumerate(expected, start=1):
        path = series / f"{subject}_{task}_{wrist}.txt"
        if not path.is_file():
            logger.warning("Missing %s", path.name)
            run.n_missing += 1
            continue
        keys = {"subject": subject, "group": groups[subject], "task": task, "wrist": WRISTS[wrist]}
        compare_file(run, replay, path, keys, by_file.get((subject, task, WRISTS[wrist]), empty))
        run.n_files += 1
        if i % 500 == 0:
            logger.info("Compared %d of %d files", i, len(expected))
    return run


def count_differences(run: Run) -> tuple[pd.DataFrame, list[str]]:
    """Return the count rows that differ from pads_counts.csv, and any row that the listed windows do not explain."""
    c_windows = pd.concat(run.c_windows, ignore_index=True)
    ours = count_windows(c_windows).set_index(["task", "group", "wrist"])
    theirs = pd.read_csv(RESULTS / "pads_counts.csv").set_index(["task", "group", "wrist"])
    if not ours.index.equals(theirs.index):
        fail("the C count rows do not line up with pads_counts.csv")
    differs = ours[(ours["windows"] != theirs["windows"]) | (ours["fired"] != theirs["fired"])].copy()
    differs["toolbox_windows"] = theirs.loc[differs.index, "windows"]
    differs["toolbox_fired"] = theirs.loc[differs.index, "fired"]

    explained: dict[tuple[str, str, str], int] = {}
    for item in run.differs:
        if not item.match.near_cut_off:
            continue
        shift = int(item.c["pred_tremor_checked"]) - int(item.toolbox["pred_tremor_checked"])
        for wrist in (item.keys["wrist"], "both"):
            key = (item.keys["task"], item.keys["group"], wrist)
            explained[key] = explained.get(key, 0) + shift
    unexplained = []
    for key, row in differs.iterrows():
        shift = int(row["fired"]) - int(row["toolbox_fired"])
        if row["windows"] != row["toolbox_windows"] or explained.get(key, 0) != shift:
            unexplained.append(" ".join(key))
    return differs.reset_index(), unexplained


def table_hash() -> str:
    """Return DET_MODEL_SHA256 from core/detector_tables.h."""
    found = re.search(r'#define DET_MODEL_SHA256 "([0-9a-f]{64})"', TABLES.read_text(encoding="ascii"))
    if found is None:
        fail("core/detector_tables.h holds no DET_MODEL_SHA256")
    return found.group(1)


def window_lines(run: Run) -> list[str]:
    """Return the table rows for every window where an answer or the peak differs."""
    lines = [
        "| Subject | Task | Wrist | Window | Toolbox probability | Toolbox sum | Peak gap | Toolbox tremor, rest, peak "
        "| C tremor, rest, peak | Near a cut-off | Passed |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |",
    ]
    for item in run.differs:
        tb, c, match = item.toolbox, item.c, item.match
        lines.append(
            f"| {item.keys['subject']} | {item.keys['task']} | {item.keys['wrist']} | {item.window} "
            f"| {tb['pred_tremor_proba']:.9f} | {tb['below_tremor_power']:.6f} | {tb['peak_gap']:.3g} "
            f"| {int(tb['pred_tremor_checked'])}, {int(tb['pred_arm_at_rest'])}, {tb['freq_peak']} "
            f"| {int(c['pred_tremor_checked'])}, {int(c['pred_arm_at_rest'])}, {c['freq_peak']} "
            f"| {'yes' if match.near_cut_off else 'no'} | {'yes' if match.passed else 'no'} |"
        )
    return lines


def count_lines(differs: pd.DataFrame) -> list[str]:
    """Return the table rows for every count row that differs from pads_counts.csv."""
    lines = [
        "| Task | Group | Wrist | C windows | Toolbox windows | C fired | Toolbox fired |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in differs.itertuples():
        lines.append(f"| {row.task} | {row.group} | {row.wrist} | {row.windows} | {row.toolbox_windows} "
                     f"| {row.fired} | {row.toolbox_fired} |")
    return lines


def write_report(run: Run, differs: pd.DataFrame, unexplained: list[str], passed: bool, path: Path) -> None:
    """Write the match report as Markdown."""
    n_answer = sum(1 for item in run.differs if item.match.answer_differs)
    n_peak = sum(1 for item in run.differs if item.match.peak_differs)
    lines = [
        "# PADS match of the C detector",
        "",
        f"- The run date is {datetime.date.today().isoformat()}.",
        f"- The toolbox is ParaDigMa {importlib.metadata.version('paradigma')} "
        f"with scikit-learn {importlib.metadata.version('scikit-learn')}.",
        f"- The model file's SHA-256 hash is {hashlib.sha256(MODEL_FILE.read_bytes()).hexdigest()}.",
        f"- DET_MODEL_SHA256 in core/detector_tables.h is {table_hash()}.",
        f"- KISS FFT is {KISS_FFT}.",
        f"- The run compared {run.n_files} files and {run.n_windows} windows, and {run.n_missing} files were missing.",
        f"- The toolbox run gave the same probability, low-frequency sum, peak, and answers as "
        f"reference/results/pads_windows.csv on all {run.n_windows} windows.",
        f"- Replay window 4k was compared with the toolbox's window k. Replay gave {run.n_extra} windows "
        "more or fewer than the toolbox on the 4 s grid.",
        f"- The largest difference in the 12 numbers is {run.mfcc_diff:.3g}, and the limit is {LIMIT}.",
        f"- The largest difference in the probability is {run.prob_diff:.3g}, and the limit is {LIMIT}.",
        f"- The largest relative difference in the low-frequency sum is {run.below_rel:.3g}. It has no limit.",
        f"- {run.n_near} windows are near a cut-off under requirement 27 of feature 4.",
        f"- An answer differs on {n_answer} windows, and the peak differs on {n_peak} windows.",
        f"- {run.n_failed} windows or files failed the match rule.",
        f"- {len(differs)} of the 99 count rows differ from reference/results/pads_counts.csv, "
        f"and {len(unexplained)} of them are not explained by the windows listed below.",
        f"- The result is {'pass' if passed else 'fail'}.",
        "",
        "## Windows where an answer or the peak differs",
        "",
    ]
    lines += window_lines(run) if run.differs else ["No window has a different answer or peak."]
    lines += ["", "## Count rows that differ from pads_counts.csv", ""]
    lines += count_lines(differs) if len(differs) else ["Every count row equals pads_counts.csv."]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    """Read the command-line options."""
    parser = argparse.ArgumentParser(description="Check the C detector against the toolbox on every PADS file.")
    parser.add_argument("--data", type=Path, default=Path("data/pads"), help="PADS 1.0.0 folder")
    parser.add_argument("--replay", type=Path, default=Path("build/core/replay"), help="the replay program")
    parser.add_argument("--out", type=Path, default=Path("tests/pads/pads_match.md"), help="the report to write")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the match, write the report, and exit with code 0 only when every check passes."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    if not args.replay.is_file():
        fail(f"replay is not at {args.replay}. Build it first with cmake.")
    run = run_match(args.data, args.replay)
    differs, unexplained = count_differences(run)
    passed = run.n_failed == 0 and run.n_missing == 0 and not unexplained
    write_report(run, differs, unexplained, passed, args.out)
    logger.info("Compared %d files and %d windows. Largest probability difference %.3g. Result %s.",
                run.n_files, run.n_windows, run.prob_diff, "pass" if passed else "fail")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
