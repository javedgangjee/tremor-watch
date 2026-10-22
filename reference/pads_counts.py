"""Count how often the ParaDigMa tremor detector fires on each PADS task, group, and wrist.

Each recording runs on its own through the toolbox's tremor features and tremor
detection with the default TremorConfig. The gyroscope is converted from radians
per second with the toolbox's own function, and the first half second is cut.
The time column is the row number divided by 100 after the cut, so the toolbox
sees the same input as the C replay program.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.metadata
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import paradigma
from paradigma.config import TremorConfig
from paradigma.pipelines.tremor_pipeline import detect_tremor, extract_tremor_features
from paradigma.util import convert_units_gyroscope

log = logging.getLogger("pads_counts")

PADS_VERSION = "1.0.0"
FS = 100
CUT_ROWS = 50  # the first half second holds the watch's start vibration
WINDOW_ROWS = 400
GYRO_COLUMNS = [4, 5, 6]  # PADS columns are time, three accelerometer axes, three gyroscope axes
TASKS = (
    "Relaxed", "RelaxedTask", "StretchHold", "LiftHold", "HoldWeight", "PointFinger",
    "DrinkGlas", "CrossArms", "TouchIndex", "TouchNose", "Entrainment",
)
WRISTS = {"LeftWrist": "left", "RightWrist": "right"}
GROUPS = {0: "healthy", 1: "Parkinson's", 2: "other movement disorder"}
WRIST_VIEWS = ("left", "right", "both")
MODEL_FILE = Path(paradigma.__file__).parent / "assets" / "tremor_detection_clf_package.pkl"

WINDOW_COLUMNS = [
    "subject", "group", "task", "wrist", "window", "pred_tremor_proba",
    "below_tremor_power", "freq_peak", "pred_arm_at_rest", "pred_tremor_checked",
]
COUNT_COLUMNS = ["task", "group", "wrist", "windows", "fired", "share"]


def parse_name(path: Path) -> tuple[str, str, str]:
    """Return the subject, task, and wrist from a name like 001_Relaxed_LeftWrist.txt."""
    subject, task, wrist = path.stem.split("_")
    if task not in TASKS or wrist not in WRISTS:
        raise ValueError(f"Unknown task or wrist in {path.name}")
    return subject, task, WRISTS[wrist]


def group_of(label: int) -> str:
    """Return the group name for a PADS label."""
    if label not in GROUPS:
        raise ValueError(f"Unknown PADS label {label}")
    return GROUPS[label]


def load_groups(file_list: Path) -> dict[str, str]:
    """Map each subject id in the PADS file list to its group."""
    table = pd.read_csv(file_list, dtype={"id": str})
    return {row.id: group_of(int(row.label)) for row in table.itertuples()}


def read_gyroscope(path: Path) -> np.ndarray:
    """Read the three gyroscope columns of a PADS recording in degrees per second."""
    rad_s = pd.read_csv(path, header=None, usecols=GYRO_COLUMNS).to_numpy(dtype=np.float64)
    return convert_units_gyroscope(rad_s, "rad/s")


def cut_start(gyro: np.ndarray) -> np.ndarray:
    """Drop the first half second of a recording."""
    return gyro[CUT_ROWS:]


def toolbox_windows(gyro: np.ndarray) -> pd.DataFrame:
    """Run the toolbox on one recording at 100 Hz and return one row per 4 second window."""
    columns = ["pred_tremor_proba", "below_tremor_power", "freq_peak",
               "pred_arm_at_rest", "pred_tremor_checked"]
    if len(gyro) < WINDOW_ROWS:
        return pd.DataFrame(columns=["window", *columns])
    config = TremorConfig()
    frame = pd.DataFrame(gyro, columns=config.gyroscope_colnames)
    frame.insert(0, config.time_colname, np.arange(len(gyro)) / FS)
    features = extract_tremor_features(frame, config)
    out = detect_tremor(features, config, MODEL_FILE)
    result = out[columns].reset_index(drop=True)
    result.insert(0, "window", np.arange(len(result)))
    return result


def process_file(path: Path, group: str) -> pd.DataFrame:
    """Return the window rows for one PADS recording."""
    subject, task, wrist = parse_name(path)
    windows = toolbox_windows(cut_start(read_gyroscope(path)))
    windows.insert(0, "wrist", wrist)
    windows.insert(0, "task", task)
    windows.insert(0, "group", group)
    windows.insert(0, "subject", subject)
    return windows[WINDOW_COLUMNS]


def count_windows(windows: pd.DataFrame) -> pd.DataFrame:
    """Count windows and fired windows for every task, group, and wrist view."""
    per_wrist = (
        windows.groupby(["task", "group", "wrist"])["pred_tremor_checked"]
        .agg(windows="size", fired="sum")
        .reset_index()
    )
    both = per_wrist.groupby(["task", "group"])[["windows", "fired"]].sum().reset_index()
    both["wrist"] = "both"
    counts = pd.concat([per_wrist, both], ignore_index=True).set_index(["task", "group", "wrist"])
    full = pd.MultiIndex.from_product([TASKS, list(GROUPS.values()), WRIST_VIEWS],
                                      names=["task", "group", "wrist"])
    counts = counts.reindex(full, fill_value=0).reset_index()
    counts[["windows", "fired"]] = counts[["windows", "fired"]].astype(int)
    counts["share"] = counts["fired"] / counts["windows"].where(counts["windows"] > 0)
    return counts[COUNT_COLUMNS]


def run_counts(data: Path) -> tuple[pd.DataFrame, pd.DataFrame, int, int]:
    """Run every expected PADS recording. Return the windows, the counts, and files read and missing."""
    groups = load_groups(data / "preprocessed" / "file_list.csv")
    series = data / "movement" / "timeseries"
    parts: list[pd.DataFrame] = []
    n_read, n_missing = 0, 0
    expected = [(s, t, w) for s in groups for t in TASKS for w in WRISTS]
    for i, (subject, task, wrist) in enumerate(expected, start=1):
        path = series / f"{subject}_{task}_{wrist}.txt"
        try:
            parts.append(process_file(path, groups[subject]))
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as err:
            log.warning("Skipped %s: %s", path.name, err)
            n_missing += 1
            continue
        n_read += 1
        if i % 500 == 0:
            log.info("Ran %d of %d files", i, len(expected))
    windows = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=WINDOW_COLUMNS)
    windows["pred_tremor_checked"] = windows["pred_tremor_checked"].astype(int)
    return windows, count_windows(windows), n_read, n_missing


def model_hash() -> str:
    """Return the SHA-256 hash of the toolbox's model file."""
    return hashlib.sha256(MODEL_FILE.read_bytes()).hexdigest()


def write_report(counts: pd.DataFrame, n_read: int, n_missing: int, path: Path) -> None:
    """Write the count table and the run details as Markdown."""
    lines = [
        "# PADS tremor counts",
        "",
        f"- The run date is {datetime.date.today().isoformat()}.",
        f"- The toolbox is ParaDigMa {importlib.metadata.version('paradigma')} "
        f"with scikit-learn {importlib.metadata.version('scikit-learn')}.",
        f"- The model file's SHA-256 hash is {model_hash()}.",
        f"- The data is PADS {PADS_VERSION}.",
        f"- The run read {n_read} files, and {n_missing} files were missing or unreadable.",
        "- Each recording ran on its own with the default TremorConfig, after the first 50 rows were cut.",
        "- A window fired when the toolbox's pred_tremor_checked is 1.",
        "",
        "The share is the part of windows in which the toolbox fired. It is not a hit rate in the "
        "Parkinson's or other movement disorder columns, because PADS does not say when tremor was "
        "present. A patient window that did not fire may hold no tremor.",
        "",
        "| Task | Group | Wrist | Windows | Fired | Share |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in counts.itertuples():
        share = "-" if pd.isna(row.share) else f"{row.share:.4f}"
        lines.append(f"| {row.task} | {row.group} | {row.wrist} | {row.windows} | {row.fired} | {share} |")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", type=Path, default=Path("data/pads"), help="PADS 1.0.0 folder")
    parser.add_argument("--out", type=Path, default=Path("reference/results"), help="output folder")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    windows, counts, n_read, n_missing = run_counts(args.data)
    args.out.mkdir(parents=True, exist_ok=True)
    windows.to_csv(args.out / "pads_windows.csv", index=False)
    counts.to_csv(args.out / "pads_counts.csv", index=False)
    write_report(counts, n_read, n_missing, args.out / "pads_counts.md")
    log.info("Read %d files, %d missing, %d windows", n_read, n_missing, len(windows))


if __name__ == "__main__":
    main()
