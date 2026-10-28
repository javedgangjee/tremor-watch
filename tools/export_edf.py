"""Export a saved recording from the watch as EDF+ files.

The tool runs in the reference venv and needs only numpy and the laptop
build of replay. Run it from the repo root after the C build.

    reference/.venv/bin/python tools/export_edf.py RECORDING [--out-dir DIR] [--boot ID] [--replay PATH]

RECORDING is a file that `tools/watch_cli.py record` saved. A name that ends
in .gz is read as gzip text, and any other name as plain text. The tool
writes one file for each boot that has replay samples, named
<stem>_<boot ID>.edf, where the stem is the recording's name without its
suffixes. The files go in the recording's folder, or in DIR. `--boot ID`
writes only that boot. The tool never writes over a file.

Each file holds the 100 Hz gyroscope samples that replay gives, which are the
samples the detector used, with one data record a second. Each replay
stretch is a segment, and a file with a gap between segments is EDF+D. The
watch's answers, face changes, doses, and stretch starts are annotations. The
boot's CLOCK line gives the start date and time, and a boot with no clock
gets the EDF+ placeholders. specs/features/13-edf-export/requirements.md
gives the rules, and tools/edfplus.py writes the bytes.
"""
from __future__ import annotations

import argparse
import gzip
import logging
import re
import subprocess
import sys
import tempfile
import zlib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np

import edfplus
from recording_text import read_recording, record_patterns

logger = logging.getLogger("export_edf")

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REPLAY = REPO / "build" / "core" / "replay"

PATTERNS = record_patterns()
# The watch writes this line when it applies a CLOCK command, as take_command()
# in firmware/main/state_task.c does. It is a diagnostic line, so the table in
# core/recording_format.md does not give its pattern.
CLOCK_LINE = re.compile(r"^CLOCK at_us=(-?\d+) offset_us=(-?\d+) local_us=(-?\d+)$")
CLOCK_WORD = re.compile(r"^CLOCK( |$)")

US_PER_SECOND = 1_000_000
US_PER_MINUTE = 60 * US_PER_SECOND
MINUTES_PER_DAY = 24 * 60
EPOCH = datetime(1970, 1, 1)

SAMPLE_HZ = 100
RECORD_SECONDS = 1
RECORD_US = RECORD_SECONDS * US_PER_SECOND
SAMPLES_PER_RECORD = SAMPLE_HZ * RECORD_SECONDS
WINDOW_US = 4 * US_PER_SECOND
# One digital step is one raw count, 1/32 degree a second. The top is
# 32764 / 32 = 1023.875, because 32767 / 32 needs 10 characters and the
# header field holds 8.
COUNTS_PER_DPS = 32
DIGITAL_MIN = -32768
DIGITAL_MAX = 32764
PHYSICAL_MIN = "-1024"
PHYSICAL_MAX = "1023.875"

RES_SENSOR_FAULT = 4
# The names that res_name() in core/window.c and face_name() in core/face.c give.
RESULT_NAMES = {0: "tremor", 1: "no tremor", 2: "arm moving", 3: "warming up"}
FACE_NAMES = {0: "Tremor Detected", 1: "Rest", 2: "Arm moving", 3: "Waiting", 4: "Dose due"}

PATIENT = "X X X X"
EQUIPMENT = "Tremor_log_watch"


def gyroscope_signal(axis: str) -> edfplus.SignalSpec:
    """Describe one gyroscope axis, with one digital step per raw count."""
    return edfplus.SignalSpec(
        label=f"Gyroscope {axis}",
        transducer="QMI8658 gyroscope",
        unit="deg/s",
        physical_min=PHYSICAL_MIN,
        physical_max=PHYSICAL_MAX,
        digital_min=str(DIGITAL_MIN),
        digital_max=str(DIGITAL_MAX),
        prefiltering="None. Resampled to 100 Hz by cubic spline",
        samples_per_record=SAMPLES_PER_RECORD,
    )


SIGNALS = tuple(gyroscope_signal(axis) for axis in "XYZ")


class ExportError(Exception):
    """A problem that stops the run with exit code 1."""


@dataclass(frozen=True)
class Clock:
    """A boot's clock: local time in microseconds since 1970 is the timer value plus offset_us."""

    at_us: int
    offset_us: int


@dataclass
class BootEvents:
    """The lines of one boot that the export uses."""

    boot_id: int
    firmware: int
    s_t0: dict[int, int] = field(default_factory=dict)
    answers: dict[tuple[int, int], int] = field(default_factory=dict)
    sensor_faults: int = 0
    faces: list[tuple[int, int]] = field(default_factory=list)
    doses: list[tuple[int, int | None]] = field(default_factory=list)
    clock: Clock | None = None
    bad_clocks: int = 0
    bad_lines: int = 0


@dataclass(frozen=True)
class Segment:
    """One replay stretch: its number, its t0, and its samples in degrees a second, shape (n, 3)."""

    stretch: int
    t0_us: int
    samples: np.ndarray


@dataclass(frozen=True)
class BootSummary:
    """What the log says about one exported boot."""

    boot_id: int
    records: int
    continuous: bool
    start: str
    has_clock: bool
    annotations: Mapping[str, int]
    clipped: int
    not_placed: Mapping[int, int]
    sensor_faults: int
    bad_clocks: int
    bad_lines: int


def record_kind(line: str) -> str:
    """Give the letter of a line that starts with a record letter and a comma, or an empty text."""
    if len(line) >= 2 and line[1] == "," and line[0] in PATTERNS:
        return line[0]
    return ""


def start_boot(boots: list[BootEvents], boot_id: int, firmware: int) -> None:
    """Start a new boot, or carry on after a repeated B line of the same boot."""
    if boots and boots[-1].boot_id == boot_id:
        return
    if any(b.boot_id == boot_id for b in boots):
        raise ExportError(
            f"boot {boot_id} comes back after boot {boots[-1].boot_id}, and replay's samples cannot tell them apart"
        )
    boots.append(BootEvents(boot_id, firmware))


def take_clock(boot: BootEvents, line: str) -> None:
    """Keep the boot's first good CLOCK line, and count a bad one."""
    found = CLOCK_LINE.match(line)
    if found is None:
        boot.bad_clocks += 1
        return
    at_us, offset_us, local_us = (int(v) for v in found.groups())
    if local_us != at_us + offset_us:
        boot.bad_clocks += 1
    elif boot.clock is None:
        boot.clock = Clock(at_us, offset_us)


def take_record(boot: BootEvents, kind: str, values: Sequence[str]) -> None:
    """Keep the values of an S, W, F, or D line."""
    if kind == "S":
        boot.s_t0[int(values[0])] = int(values[2])
    elif kind == "W":
        code = int(values[2])
        if values[1] == "" or code == RES_SENSOR_FAULT:
            boot.sensor_faults += 1
        else:
            boot.answers[(int(values[0]), int(values[1]))] = code
    elif kind == "F":
        boot.faces.append((int(values[0]), int(values[1])))
    elif kind == "D":
        boot.doses.append((int(values[0]), int(values[1]) if values[1] else None))


def read_events(lines: Sequence[str]) -> list[BootEvents]:
    """Read each boot's lines with the rules of core/recording_format.md.

    Lines before the first B line, laptop lines, and other lines that are not
    record lines are skipped. A record line that breaks its pattern counts as
    bad. The last S line of each stretch and the last W line of each window hold.
    """
    boots: list[BootEvents] = []
    for line in lines:
        kind = record_kind(line)
        if not boots and kind != "B":
            continue
        if not kind:
            if CLOCK_WORD.match(line):
                take_clock(boots[-1], line)
            continue
        found = PATTERNS[kind].match(line)
        if found is None:
            if boots:
                boots[-1].bad_lines += 1
            continue
        if kind == "B":
            start_boot(boots, int(found.group(1)), int(found.group(3)))
        else:
            take_record(boots[-1], kind, found.groups())
    return boots


def window_t0s(stdout: str) -> dict[tuple[int, int], int]:
    """Read the t0 of each (boot, stretch) from replay's window rows."""
    rows = stdout.splitlines()
    if not rows:
        return {}
    columns = rows[0].split(",")
    boot, stretch, t0 = (columns.index(name) for name in ("boot", "stretch", "t0_us"))
    t0s: dict[tuple[int, int], int] = {}
    for row in rows[1:]:
        values = row.split(",")
        t0s[(int(values[boot]), int(values[stretch]))] = int(values[t0])
    return t0s


def run_replay(replay: Path, lines: Sequence[str]) -> tuple[dict[tuple[int, int], int], np.ndarray, str]:
    """Run replay on the lines and give the t0 of each (boot, stretch), the samples, and its summary line.

    The samples have the columns boot, stretch, sample, and x, y, and z in
    degrees a second, as 64-bit floats.
    """
    if not replay.is_file():
        raise ExportError(f"replay is not at {replay}. Build it first with cmake.")
    text = "".join(line + "\n" for line in lines)
    with tempfile.TemporaryDirectory() as folder:
        samples_file = Path(folder) / "samples.csv"
        ran = subprocess.run(
            [str(replay), "--recording", "-", "--samples", str(samples_file)],
            input=text, capture_output=True, text=True, check=False,
        )
        if ran.returncode != 0:
            raise ExportError(f"replay exited with code {ran.returncode}: {ran.stderr.strip()}")
        samples = np.loadtxt(samples_file, delimiter=",", skiprows=1, dtype=np.float64, ndmin=2)
    summary = next((row for row in ran.stderr.splitlines() if row.startswith("replay: lines=")), ran.stderr.strip())
    return window_t0s(ran.stdout), samples.reshape(-1, 6), summary


def segments_for(boot_id: int, t0s: Mapping[tuple[int, int], int], samples: np.ndarray) -> list[Segment]:
    """Give the replay stretches of one boot as segments in time order.

    Each stretch's samples must run from 0 up with no hole and fill whole
    data records.
    """
    mine = samples[samples[:, 0] == boot_id]
    numbers, firsts = np.unique(mine[:, 1].astype(np.int64), return_index=True)
    segments: list[Segment] = []
    for number in numbers[np.argsort(firsts)].tolist():
        rows = mine[mine[:, 1] == number]
        if (boot_id, number) not in t0s:
            raise ExportError(f"replay gave samples for boot {boot_id} stretch {number} but no window row")
        if not np.array_equal(rows[:, 2], np.arange(len(rows))):
            raise ExportError(f"replay's samples of boot {boot_id} stretch {number} do not run from 0 with no hole")
        if len(rows) % SAMPLES_PER_RECORD:
            raise ExportError(
                f"replay's {len(rows)} samples of boot {boot_id} stretch {number} "
                f"are not a whole number of {SAMPLES_PER_RECORD}"
            )
        segments.append(Segment(number, t0s[(boot_id, number)], rows[:, 3:6].astype(np.float32)))
    return sorted(segments, key=lambda s: s.t0_us)


def record_onsets(segments: Sequence[Segment]) -> np.ndarray:
    """Give the timer value of each data record's start: t0 + j seconds within each segment."""
    return np.concatenate([
        s.t0_us + RECORD_US * np.arange(len(s.samples) // SAMPLES_PER_RECORD, dtype=np.int64) for s in segments
    ])


def digital_records(segments: Sequence[Segment]) -> tuple[np.ndarray, int]:
    """Give the digital samples of shape (records, 3, 100) as int16, and the number clipped.

    Each value is 32 x rounded half to even and clipped to the digital range.
    """
    x = np.concatenate([s.samples for s in segments])
    steps = np.rint(x * COUNTS_PER_DPS)
    clipped = int(np.count_nonzero((steps < DIGITAL_MIN) | (steps > DIGITAL_MAX)))
    digital = np.clip(steps, DIGITAL_MIN, DIGITAL_MAX).astype(np.int16)
    return digital.reshape(-1, SAMPLES_PER_RECORD, len(SIGNALS)).transpose(0, 2, 1), clipped


def local_datetime(local_us: int) -> datetime:
    return EPOCH + timedelta(microseconds=local_us)


def file_start(first_record_us: int, clock: Clock | None) -> tuple[int, date | None, time | None]:
    """Give the file's start on the timer and the header's date and time.

    With a clock, the file starts at the whole second of local time at or
    before the first data record. Without one, it starts at the first record.
    """
    if clock is None:
        return first_record_us, None, None
    local_start_us = (first_record_us + clock.offset_us) // US_PER_SECOND * US_PER_SECOND
    start = local_datetime(local_start_us)
    return local_start_us - clock.offset_us, start.date(), start.time()


def dose_text(local_us: int | None) -> str:
    if local_us is None:
        return "Dose taken with no dose time"
    minutes = local_us // US_PER_MINUTE % MINUTES_PER_DAY
    return f"Dose taken for {minutes // 60:02d}:{minutes % 60:02d}"


def annotations_for(
    events: BootEvents, start_us: int
) -> tuple[list[edfplus.Annotation], dict[str, int], dict[int, int]]:
    """Give the boot's annotations with onsets from start_us, their counts by kind, and unplaced W lines.

    The last count maps each stretch with W lines but no S line to its
    number of W lines.
    """
    found: list[edfplus.Annotation] = []
    kinds: Counter[str] = Counter()
    not_placed: Counter[int] = Counter()
    for number, t0 in sorted(events.s_t0.items()):
        found.append(edfplus.Annotation(t0 - start_us, None, f"Stretch {number} starts"))
        kinds["stretch"] += 1
    for (stretch, window), code in sorted(events.answers.items()):
        if stretch not in events.s_t0:
            not_placed[stretch] += 1
            continue
        onset = events.s_t0[stretch] + window * US_PER_SECOND - start_us
        found.append(edfplus.Annotation(onset, WINDOW_US, f"Answer {RESULT_NAMES[code]}"))
        kinds[RESULT_NAMES[code]] += 1
    for at_us, state in events.faces:
        found.append(edfplus.Annotation(at_us - start_us, None, f"Face {FACE_NAMES[state]}"))
        kinds["face"] += 1
    for at_us, local_us in events.doses:
        found.append(edfplus.Annotation(at_us - start_us, None, dose_text(local_us)))
        kinds["dose"] += 1
    return found, dict(kinds), dict(not_placed)


def header_for(events: BootEvents, start_date: date | None, start_time: time | None) -> edfplus.EdfHeader:
    recording = (
        f"Startdate {edfplus.plus_date_text(start_date)} X X {EQUIPMENT} "
        f"boot_{events.boot_id} firmware_{events.firmware}"
    )
    return edfplus.EdfHeader(PATIENT, recording, start_date, start_time, RECORD_SECONDS)


def start_text(first_record_us: int, clock: Clock | None) -> str:
    if clock is None:
        return f"timer {edfplus.seconds_text(first_record_us, signed=False)} s with no clock"
    return f"{local_datetime(first_record_us + clock.offset_us).isoformat(sep=' ')} local time"


def export_boot(events: BootEvents, segments: Sequence[Segment]) -> tuple[bytes, BootSummary]:
    """Give one boot's EDF+ bytes and the summary for the log."""
    onsets = record_onsets(segments)
    first = int(onsets[0])
    start_us, start_date, start_time = file_start(first, events.clock)
    digital, clipped = digital_records(segments)
    annotations, kinds, not_placed = annotations_for(events, start_us)
    try:
        data = edfplus.edf_bytes(
            header_for(events, start_date, start_time), SIGNALS, digital, onsets - start_us, annotations
        )
    except edfplus.EdfError as problem:
        raise ExportError(f"boot {events.boot_id} cannot be written: {problem}") from problem
    summary = BootSummary(
        boot_id=events.boot_id,
        records=len(onsets),
        continuous=edfplus.is_continuous(onsets, RECORD_US),
        start=start_text(first, events.clock),
        has_clock=events.clock is not None,
        annotations=kinds,
        clipped=clipped,
        not_placed=not_placed,
        sensor_faults=events.sensor_faults,
        bad_clocks=events.bad_clocks,
        bad_lines=events.bad_lines,
    )
    return data, summary


def output_path(recording: Path, out_dir: Path | None, boot_id: int) -> Path:
    """Give <stem>_<boot ID>.edf in out_dir or in the recording's folder."""
    suffixes = "".join(recording.suffixes)
    stem = recording.name[: len(recording.name) - len(suffixes)] if suffixes else recording.name
    return (out_dir if out_dir is not None else recording.parent) / f"{stem}_{boot_id}.edf"


def read_lines(path: Path) -> list[str]:
    """Read the recording's lines, turn a read failure into ExportError, and warn when it was cut short."""
    try:
        lines, cut_short = read_recording(path)
    except FileNotFoundError as problem:
        raise ExportError(f"{path} does not exist") from problem
    except (gzip.BadGzipFile, zlib.error) as problem:
        raise ExportError(f"{path} is not a gzip file that can be read: {problem}") from problem
    except OSError as problem:
        raise ExportError(f"cannot read {path}: {problem}") from problem
    if cut_short:
        logger.warning("%s was cut short. The export uses the %d whole lines before the cut.", path, len(lines))
    return lines


def chosen_boots(boots: Sequence[BootEvents], boot_id: int | None) -> list[BootEvents]:
    if boot_id is None:
        return list(boots)
    chosen = [b for b in boots if b.boot_id == boot_id]
    if not chosen:
        held = ", ".join(str(b.boot_id) for b in boots)
        raise ExportError(f"the recording holds no boot {boot_id}. Its boots are {held}.")
    return chosen


def build_files(
    recording: Path, out_dir: Path | None, boots: Sequence[BootEvents], boot_id: int | None, replay: Path, lines: Sequence[str]
) -> list[tuple[Path, bytes, BootSummary]]:
    """Run replay and build each chosen boot's file in memory."""
    chosen = chosen_boots(boots, boot_id)
    t0s, samples, replay_summary = run_replay(replay, lines)
    logger.info("%s", replay_summary)
    files: list[tuple[Path, bytes, BootSummary]] = []
    for events in chosen:
        segments = segments_for(events.boot_id, t0s, samples)
        if not segments:
            if boot_id is not None:
                raise ExportError(f"boot {events.boot_id} has no samples from replay, so it cannot be exported")
            logger.info("Boot %d has no samples from replay, so it gets no file.", events.boot_id)
            continue
        data, summary = export_boot(events, segments)
        files.append((output_path(recording, out_dir, events.boot_id), data, summary))
    if not files:
        raise ExportError(f"no boot of {recording} has samples from replay, so there is nothing to export")
    return files


def log_summary(path: Path, summary: BootSummary) -> None:
    kinds = ", ".join(f"{name} {count}" for name, count in sorted(summary.annotations.items()))
    logger.info(
        "Wrote %s for boot %d: %s, %d records, start %s. Annotations: %s.",
        path, summary.boot_id, "EDF+C" if summary.continuous else "EDF+D", summary.records, summary.start, kinds,
    )
    logger.info(
        "Boot %d: clipped samples %d, windows not placed %d, sensor faults %d, bad CLOCK lines %d, bad lines %d.",
        summary.boot_id, summary.clipped, sum(summary.not_placed.values()), summary.sensor_faults,
        summary.bad_clocks, summary.bad_lines,
    )
    for stretch, count in sorted(summary.not_placed.items()):
        logger.warning("Boot %d: %d W lines of stretch %d have no S line, so they are not placed.",
                       summary.boot_id, count, stretch)
    if not summary.has_clock:
        logger.warning("Boot %d has no clock, so the header gives 01.01.85 00.00.00.", summary.boot_id)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a saved recording as EDF+ files, one for each boot.")
    parser.add_argument("recording", type=Path, help="a recording that watch_cli.py saved, as gzip or plain text")
    parser.add_argument("--out-dir", type=Path, default=None, help="the folder for the files")
    parser.add_argument("--boot", type=int, default=None, help="export only this boot ID")
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY, help="the replay program")
    return parser.parse_args(argv)


def export(args: argparse.Namespace) -> None:
    """Build every file first, check that none exists, and then write them."""
    lines = read_lines(args.recording)
    boots = read_events(lines)
    if not boots:
        raise ExportError(f"{args.recording} holds no B line, so it holds no boot")
    files = build_files(args.recording, args.out_dir, boots, args.boot, args.replay, lines)
    for path, _, _ in files:
        if path.exists():
            raise ExportError(f"{path} exists, so nothing was written")
    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
    for path, data, summary in files:
        try:
            edfplus.write_new(path, data)
        except OSError as problem:
            raise ExportError(f"cannot write {path}: {problem}") from problem
        log_summary(path, summary)


def main(argv: list[str] | None = None) -> int:
    """Export the recording and give the exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    try:
        export(args)
    except ExportError as problem:
        logger.error("%s", problem)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
