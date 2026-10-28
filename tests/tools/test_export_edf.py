"""Tests of tools/export_edf.py and tools/edfplus.py.

Cases follow check 1 of specs/features/13-edf-export/validation.md, in the
same order. They read the files back with edfio and with two small readers of
their own, which import nothing from tools/, so the writer is never checked
with its own reader. They need the laptop build of replay and edfio 0.4.18,
so they run in the reference venv after the C build.

    reference/.venv/bin/python -m pytest tests/tools/test_export_edf.py -q
"""
from __future__ import annotations

import gzip
import logging
import re
import subprocess
import sys
import zlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import edfio
import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tests" / "replay"))
import edfplus  # noqa: E402
import export_edf  # noqa: E402
import recording_maker as rm  # noqa: E402

PY = Path(sys.executable)
TOOL = REPO / "tools" / "export_edf.py"
FIRMWARE_LOGS = REPO / "tests" / "firmware"
SYNTHETIC = REPO / "viewer" / "test" / "fixtures" / "synthetic.txt.gz"
RECORDINGS = {
    "record_log": FIRMWARE_LOGS / "record_log.txt.gz",
    "face_log": FIRMWARE_LOGS / "face_log.txt.gz",
    "command_log": FIRMWARE_LOGS / "command_log.txt.gz",
    "drop_log": FIRMWARE_LOGS / "drop_log.txt.gz",
    "synthetic": SYNTHETIC,
}

GYRO_LABELS = ["Gyroscope X", "Gyroscope Y", "Gyroscope Z"]
DIGITAL_MIN = -32768
DIGITAL_MAX = 32764
STEP = 1 / 32
ROUNDING_LIMIT = 1 / 64
ONSET_LIMIT = 1e-9
EPOCH = datetime(1970, 1, 1)
US = 1_000_000
LAPTOP_TIME = re.compile(r"^\d+\.\d{3}\t")


def digital_of(x: np.ndarray) -> np.ndarray:
    """The digital of x, as the Terms of validation.md give it."""
    return np.clip(np.rint(32 * x), DIGITAL_MIN, DIGITAL_MAX)


def local_us(when: datetime) -> int:
    return (when - EPOCH) // timedelta(microseconds=1)


# The test's TAL reader.


@dataclass(frozen=True)
class Tal:
    onset: Decimal
    duration: Decimal | None
    texts: list[str]


@dataclass(frozen=True)
class EdfRaw:
    """The raw header and each data record's TALs and annotation bytes."""

    header: bytes
    labels: list[str]
    samples: list[int]
    records: list[list[Tal]]
    annotation_bytes: list[bytes]

    @property
    def starts(self) -> list[Decimal]:
        return [tals[0].onset for tals in self.records]


def parse_tal(raw: bytes) -> Tal:
    parts = raw.split(b"\x14")
    head, _, duration = parts[0].partition(b"\x15")
    return Tal(Decimal(head.decode()), Decimal(duration.decode()) if duration else None,
               [p.decode() for p in parts[1:-1]])


def read_raw(path: Path) -> EdfRaw:
    data = path.read_bytes()
    count = int(data[252:256])
    header = data[: 256 * (count + 1)]
    labels = [header[256 + 16 * i : 256 + 16 * (i + 1)].decode().strip() for i in range(count)]
    at = 256 + count * (16 + 80 + 8 * 5 + 80)
    samples = [int(header[at + 8 * i : at + 8 * (i + 1)]) for i in range(count)]
    record_bytes = 2 * sum(samples)
    ann_from = 2 * sum(samples[:-1])
    records: list[list[Tal]] = []
    annotation_bytes: list[bytes] = []
    for j in range(int(header[236:244])):
        record = data[len(header) + j * record_bytes : len(header) + (j + 1) * record_bytes]
        ann = record[ann_from:]
        annotation_bytes.append(ann)
        records.append([parse_tal(t) for t in ann.rstrip(b"\x00").split(b"\x00")])
    return EdfRaw(header, labels, samples, records, annotation_bytes)


# The test's line reader.


@dataclass
class Boot:
    boot_id: int
    s_t0: dict[int, int] = field(default_factory=dict)
    windows: dict[tuple[int, int], int] = field(default_factory=dict)
    faces: list[tuple[int, int]] = field(default_factory=list)
    doses: list[tuple[int, str]] = field(default_factory=list)
    clocks: list[tuple[int, int, int]] = field(default_factory=list)


def text_lines(path: Path) -> list[str]:
    raw = gzip.decompress(path.read_bytes()).decode().splitlines()
    return [LAPTOP_TIME.sub("", line) for line in raw]


def read_boots(lines: Sequence[str]) -> list[Boot]:
    boots: list[Boot] = []
    for line in lines:
        if (m := re.match(r"^B,(\d+),\d+,\d+,[0-9a-f]{64}$", line)) is not None:
            if not boots or boots[-1].boot_id != int(m.group(1)):
                boots.append(Boot(int(m.group(1))))
        elif not boots:
            continue
        elif (m := re.match(r"^S,(\d+),\d+,(-?\d+),\d+,\d+$", line)) is not None:
            boots[-1].s_t0[int(m.group(1))] = int(m.group(2))
        elif (m := re.match(r"^W,(\d+),(\d+),([0-3]),", line)) is not None:
            boots[-1].windows[(int(m.group(1)), int(m.group(2)))] = int(m.group(3))
        elif (m := re.match(r"^F,(-?\d+),([0-4])$", line)) is not None:
            boots[-1].faces.append((int(m.group(1)), int(m.group(2))))
        elif (m := re.match(r"^D,(-?\d+),(-?\d*)$", line)) is not None:
            boots[-1].doses.append((int(m.group(1)), m.group(2)))
        elif (m := re.match(r"^CLOCK at_us=(-?\d+) offset_us=(-?\d+) local_us=(-?\d+)$", line)) is not None:
            boots[-1].clocks.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return boots


def boot_of(lines: Sequence[str], boot_id: int) -> Boot:
    return next(b for b in read_boots(lines) if b.boot_id == boot_id)


# Replay and the export.


@dataclass(frozen=True)
class Replayed:
    """Replay's samples as float32, shape (n, 6), and the t0 of each (boot, stretch)."""

    samples: np.ndarray
    t0s: dict[tuple[int, int], int]

    def axes(self, boot_id: int) -> np.ndarray:
        return self.samples[self.samples[:, 0] == boot_id][:, 3:6]

    def stretch_count(self, boot_id: int, stretch: int) -> int:
        mine = self.samples[self.samples[:, 0] == boot_id]
        return int(np.count_nonzero(mine[:, 1] == stretch))


def replay_of(lines: Sequence[str], folder: Path) -> Replayed:
    out = folder / "replay_samples.csv"
    rows, stderr, code = rm.replay_rows(lines, ["--samples", str(out)])
    assert code == 0, stderr
    samples = np.loadtxt(out, delimiter=",", skiprows=1, dtype=np.float64, ndmin=2).reshape(-1, 6)
    t0s = {(int(r.boot), int(r.stretch)): int(r.t0_us) for r in rows.itertuples()}
    return Replayed(samples.astype(np.float32), t0s)


@dataclass(frozen=True)
class Exported:
    code: int
    log: str
    out: Path


def export_cli(recording: Path, out: Path, *args: str) -> Exported:
    ran = subprocess.run([str(PY), str(TOOL), str(recording), "--out-dir", str(out), *args],
                         capture_output=True, text=True, check=False, cwd=REPO)
    return Exported(ran.returncode, ran.stderr, out)


def export_main(caplog: pytest.LogCaptureFixture, recording: Path, out: Path, *args: str) -> Exported:
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="export_edf"):
        code = export_edf.main([str(recording), "--out-dir", str(out), *args])
    return Exported(code, caplog.text, out)


def files_in(folder: Path) -> list[str]:
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


def save_recording(folder: Path, name: str, lines: Sequence[str]) -> Path:
    path = folder / name
    path.write_bytes(gzip.compress("".join(f"0.000\t{line}\n" for line in lines).encode()))
    return path


def annotation_counts(edf: edfio.Edf) -> Counter[str]:
    return Counter(a.text for a in edf.annotations)


def first_t_index(lines: Sequence[str]) -> int:
    return next(i for i, line in enumerate(lines) if line.startswith("T,"))


Committed = dict[str, tuple[Exported, Replayed, list[str]]]


@pytest.fixture(scope="module")
def committed(tmp_path_factory: pytest.TempPathFactory) -> Committed:
    """Export each committed recording once, and run replay once on it."""
    found: Committed = {}
    for name, path in RECORDINGS.items():
        folder = tmp_path_factory.mktemp(name)
        lines = text_lines(path)
        found[name] = (export_cli(path, folder / "D"), replay_of(lines, folder), lines)
    return found


@pytest.fixture
def made(tmp_path: Path) -> list[str]:
    """M: a made-up recording of 30 seconds with a shake of 100 degrees a second."""
    return rm.recording_lines(30, 100)


# The cases on the committed recordings.

RECORD_FILE = "record_log_2274443476.edf"


def test_01_record_log_signals(committed: Committed) -> None:
    result, _, _ = committed["record_log"]
    assert result.code == 0, result.log
    assert files_in(result.out) == [RECORD_FILE]
    edf = edfio.read_edf(result.out / RECORD_FILE)
    assert edf.reserved == "EDF+C"
    assert edf.is_continuous is True
    assert edf.num_data_records == 1801
    assert edf.data_record_duration == 1.0
    assert [s.label for s in edf.signals] == GYRO_LABELS
    for s in edf.signals:
        assert s.sampling_frequency == 100.0
        assert s.physical_dimension == "deg/s"
        assert s.transducer_type == "QMI8658 gyroscope"
        assert (s.physical_min, s.physical_max) == (-1024.0, 1023.875)
        assert (s.digital_min, s.digital_max) == (-32768, 32764)
        assert (s.physical_max - s.physical_min) / (s.digital_max - s.digital_min) == STEP


def test_02_record_log_header(committed: Committed) -> None:
    result, _, _ = committed["record_log"]
    path = result.out / RECORD_FILE
    raw = read_raw(path)
    head = raw.header
    assert head[0:8] == b"0" + b" " * 7
    assert head[8:88] == b"X X X X".ljust(80)
    assert head[88:168].startswith(b"Startdate X X X Tremor_log_watch boot_2274443476 firmware_9")
    assert head[168:184] == b"01.01.8500.00.00"
    assert head[184:192] == b"1280    "
    assert head[192:236].startswith(b"EDF+C")
    assert head[236:244] == b"1801".ljust(8)
    assert head[244:252] == b"1" + b" " * 7
    assert head[252:256] == b"4   "
    assert raw.labels == [*GYRO_LABELS, "EDF Annotations"]
    dmin_at = 256 + 4 * (16 + 80 + 8 + 8 + 8)
    assert head[dmin_at + 24 : dmin_at + 32].strip() == b"-32768"
    assert head[dmin_at + 32 + 24 : dmin_at + 32 + 32].strip() == b"32767"
    annotation_samples = raw.samples[3]
    assert len(path.read_bytes()) == 1280 + 1801 * (600 + 2 * annotation_samples)
    assert all(32 <= b <= 126 for b in head)
    edf = edfio.read_edf(path)
    with pytest.raises(edfio.AnonymizedDateError):
        _ = edf.startdate
    assert edf.starttime == time(0, 0, 0)


def test_03_record_log_annotations(committed: Committed) -> None:
    result, replayed, lines = committed["record_log"]
    raw = read_raw(result.out / RECORD_FILE)
    assert raw.starts == [Decimal(j) for j in range(1801)]
    edf = edfio.read_edf(result.out / RECORD_FILE)
    assert len(edf.annotations) == 1800
    assert annotation_counts(edf) == Counter({
        "Answer warming up": 1, "Answer no tremor": 1797, "Face Rest": 1, "Stretch 0 starts": 1,
    })
    r0 = replayed.t0s[(2274443476, 0)]
    assert r0 == 234273
    boot = boot_of(lines, 2274443476)
    answers = sorted((a for a in edf.annotations if a.text.startswith("Answer")), key=lambda a: a.onset)
    windows = sorted(boot.windows)
    assert len(answers) == len(windows) == 1798
    for a, (stretch, n) in zip(answers, windows):
        assert a.onset == pytest.approx((boot.s_t0[stretch] + n * US - r0) / US, abs=ONSET_LIMIT)
        assert a.duration == 4.0


def test_04_record_log_samples(committed: Committed) -> None:
    result, replayed, _ = committed["record_log"]
    edf = edfio.read_edf(result.out / RECORD_FILE)
    x = replayed.axes(2274443476)
    for axis, s in enumerate(edf.signals):
        expected = digital_of(x[:, axis])
        assert np.array_equal(s.digital, expected)
        assert np.array_equal(s.data, s.digital / 32)
        kept = (np.rint(32 * x[:, axis]) >= DIGITAL_MIN) & (np.rint(32 * x[:, axis]) <= DIGITAL_MAX)
        assert np.all(np.abs(x[kept, axis] - s.data[kept]) <= ROUNDING_LIMIT)


def test_05_face_log_clock(committed: Committed) -> None:
    result, replayed, lines = committed["face_log"]
    path = result.out / "face_log_2694533211.edf"
    assert result.code == 0, result.log
    edf = edfio.read_edf(path)
    assert edf.reserved == "EDF+C"
    assert edf.num_data_records == 1141
    boot = boot_of(lines, 2694533211)
    offset = boot.clocks[0][1]
    assert offset == 1792763353423973
    r0 = replayed.t0s[(2694533211, 0)]
    assert r0 == 234803
    start = EPOCH + timedelta(microseconds=r0 + offset)
    assert start == datetime(2026, 10, 23, 13, 49, 13, 658776)
    assert edf.startdatetime == start
    raw = read_raw(path)
    assert raw.header[168:184] == b"23.10.2613.49.13"
    assert raw.header[88:168].startswith(b"Startdate 23-OCT-2026 X X Tremor_log_watch boot_2694533211 firmware_11")
    assert raw.starts[0] == Decimal("0.658776")
    assert len(edf.annotations) == 1145
    texts = [a.text for a in edf.annotations]
    assert sum(t.startswith("Answer") for t in texts) == 1138
    assert sum(t.startswith("Face") for t in texts) == 6
    assert sum(t.startswith("Stretch") for t in texts) == 1
    faces = sorted((a for a in edf.annotations if a.text.startswith("Face")), key=lambda a: a.onset)
    for a, (at_us, _) in zip(faces, sorted(boot.faces), strict=True):
        assert a.onset == pytest.approx((at_us - r0) / US, abs=ONSET_LIMIT)


def test_06_command_log_two_boots(committed: Committed) -> None:
    result, replayed, _ = committed["command_log"]
    assert result.code == 0, result.log
    first, second = "command_log_3162426297.edf", "command_log_505078862.edf"
    assert files_in(result.out) == [first, second]
    edf = edfio.read_edf(result.out / first)
    assert edf.reserved == "EDF+C"
    assert edf.num_data_records == 10
    assert read_raw(result.out / first).header[88:168].startswith(b"Startdate X")
    assert len(edf.annotations) == 9
    edf = edfio.read_edf(result.out / second)
    raw = read_raw(result.out / second)
    assert raw.header[192:236].startswith(b"EDF+D")
    assert edf.num_data_records == 1258
    assert edf.is_continuous is False
    assert replayed.stretch_count(505078862, 0) // 100 == 945
    assert replayed.stretch_count(505078862, 1) // 100 == 313
    gap_start = Decimal(946328952 - 234313) / US
    expected = [Decimal(j) for j in range(945)] + [gap_start + (j - 945) for j in range(945, 1258)]
    # The boot has a clock, so the file starts at the whole second before the
    # first record, and every start is 0.243832 seconds later than j.
    assert raw.starts[0] == Decimal("0.243832")
    assert [s - raw.starts[0] for s in raw.starts] == expected
    assert edf.startdatetime == datetime(2026, 10, 23, 6, 1, 6, 243832)
    assert len(edf.annotations) == 1259


def test_07_drop_log_gap(committed: Committed) -> None:
    result, replayed, _ = committed["drop_log"]
    path = result.out / "drop_log_3492590314.edf"
    assert result.code == 0, result.log
    raw = read_raw(path)
    assert raw.header[192:236].startswith(b"EDF+D")
    assert len(raw.records) == 218
    assert replayed.stretch_count(3492590314, 0) // 100 == 69
    assert replayed.stretch_count(3492590314, 2) // 100 == 149
    assert replayed.t0s[(3492590314, 0)] == 234278
    assert replayed.t0s[(3492590314, 2)] == 130387360
    assert raw.starts[69] == Decimal(130387360 - 234278) / US
    edf = edfio.read_edf(path)
    assert len(edf.annotations) == 218
    x = replayed.axes(3492590314)
    assert len(x) == 21800
    for axis, s in enumerate(edf.signals):
        assert np.array_equal(s.digital, digital_of(x[:, axis]))


def test_08_synthetic_segments(committed: Committed) -> None:
    result, _, _ = committed["synthetic"]
    assert result.code == 0, result.log
    assert files_in(result.out) == ["synthetic_305419896.edf"]
    assert re.search(r"[Bb]oot 4294967295 has no samples", result.log)
    raw = read_raw(result.out / "synthetic_305419896.edf")
    assert raw.header[192:236].startswith(b"EDF+D")
    assert len(raw.records) == 156
    starts = raw.starts
    breaks = [0] + [j for j in range(1, len(starts)) if starts[j] - starts[j - 1] != 1] + [len(starts)]
    lengths = [b - a for a, b in zip(breaks, breaks[1:])]
    t0s = [int(starts[a] * US) + 250000 for a in breaks[:-1]]
    assert lengths == [69, 29, 19, 39]
    assert t0s == [250000, 70388948, 100599689, 120329262]


def test_09_synthetic_annotations(committed: Committed) -> None:
    result, _, lines = committed["synthetic"]
    edf = edfio.read_edf(result.out / "synthetic_305419896.edf")
    assert len(edf.annotations) == 155
    counts = annotation_counts(edf)
    assert counts["Answer tremor"] == 39
    assert counts["Answer no tremor"] == 92
    assert counts["Answer arm moving"] == 18
    assert counts["Answer warming up"] == 2
    by_text = {a.text: a for a in edf.annotations if not a.text.startswith("Answer")}
    assert by_text["Face Rest"].onset == pytest.approx(-0.25, abs=ONSET_LIMIT)
    assert by_text["Dose taken with no dose time"].onset == pytest.approx(19.75, abs=ONSET_LIMIT)
    assert by_text["Stretch 0 starts"].onset == pytest.approx(0, abs=ONSET_LIMIT)
    assert by_text["Stretch 1 starts"].onset == pytest.approx((120329262 - 250000) / US, abs=ONSET_LIMIT)
    assert re.search(r"sensor faults 1\b", result.log)
    assert re.search(r"windows not placed 0\b", result.log)
    boot = boot_of(lines, 305419896)
    tremor = sorted(k for k, code in boot.windows.items() if code == 0)
    assert tremor == [(0, n) for n in range(30, 57)] + [(1, n) for n in range(10, 22)]
    found = sorted((a.onset, a.duration) for a in edf.annotations if a.text == "Answer tremor")
    expected = sorted(((boot.s_t0[s] + n * US - 250000) / US, 4.0) for s, n in tremor)
    for (onset, duration), (want, want_duration) in zip(found, expected, strict=True):
        assert onset == pytest.approx(want, abs=ONSET_LIMIT)
        assert duration == want_duration


def test_10_synthetic_annotation_places(committed: Committed) -> None:
    result, _, _ = committed["synthetic"]
    raw = read_raw(result.out / "synthetic_305419896.edf")
    starts = raw.starts
    for j, (tals, ann) in enumerate(zip(raw.records, raw.annotation_bytes)):
        assert tals[0].duration is None and tals[0].texts == [""]
        body = ann.rstrip(b"\x00")
        assert ann.startswith(f"+{tals[0].onset}".encode() + b"\x14\x14\x00")
        assert body.endswith(b"\x14")
        assert set(ann[len(body) :]) <= {0}
        onsets = [t.onset for t in tals[1:]]
        assert onsets == sorted(onsets)
        for onset in onsets:
            home = max([i for i, s in enumerate(starts) if s <= onset], default=0)
            assert home == j


# The cases on made-up recordings.


def clock_line(r0_local: datetime, at_us: int = 1_000_000) -> str:
    offset = local_us(r0_local) - rm.T0_US
    return f"CLOCK at_us={at_us} offset_us={offset} local_us={at_us + offset}"


def test_11_clock_header(caplog: pytest.LogCaptureFixture, tmp_path: Path, made: list[str]) -> None:
    lines = [made[0], clock_line(datetime(2026, 10, 28, 9, 15, 42, 500000)), *made[1:]]
    result = export_main(caplog, save_recording(tmp_path, "m.txt.gz", lines), tmp_path / "D")
    assert result.code == 0, result.log
    raw = read_raw(tmp_path / "D" / f"m_{rm.BOOT_ID}.edf")
    assert raw.header[168:184] == b"28.10.2609.15.42"
    assert raw.header[88:168].startswith(b"Startdate 28-OCT-2026 ")
    assert raw.starts[0] == Decimal("0.5")


def test_12_year_after_2084(caplog: pytest.LogCaptureFixture, tmp_path: Path, made: list[str]) -> None:
    lines = [made[0], clock_line(datetime(2090, 6, 1, 12, 0, 0)), *made[1:]]
    result = export_main(caplog, save_recording(tmp_path, "m.txt.gz", lines), tmp_path / "D")
    assert result.code == 0, result.log
    raw = read_raw(tmp_path / "D" / f"m_{rm.BOOT_ID}.edf")
    assert raw.header[168:176] == b"01.06.yy"
    assert raw.header[88:168].startswith(b"Startdate 01-JUN-2090 ")


def test_13_bad_clock(caplog: pytest.LogCaptureFixture, tmp_path: Path, made: list[str]) -> None:
    lines = [made[0], "CLOCK at_us=1 offset_us=2 local_us=4", *made[1:]]
    result = export_main(caplog, save_recording(tmp_path, "m.txt.gz", lines), tmp_path / "D")
    assert result.code == 0, result.log
    raw = read_raw(tmp_path / "D" / f"m_{rm.BOOT_ID}.edf")
    assert raw.header[88:168].startswith(b"Startdate X ")
    assert raw.header[168:184] == b"01.01.8500.00.00"
    assert re.search(r"bad CLOCK lines 1\b", result.log)


def test_14_doses(caplog: pytest.LogCaptureFixture, tmp_path: Path, made: list[str]) -> None:
    d1 = (20000 * 24 * 3600 + 8 * 3600 + 30 * 60) * US
    at = first_t_index(made) + 1
    lines = [*made[:at], f"D,15000000,{d1}", "D,16000000,", *made[at:]]
    result = export_main(caplog, save_recording(tmp_path, "m.txt.gz", lines), tmp_path / "D")
    assert result.code == 0, result.log
    edf = edfio.read_edf(tmp_path / "D" / f"m_{rm.BOOT_ID}.edf")
    doses = {a.text: a for a in edf.annotations if a.text.startswith("Dose")}
    assert set(doses) == {"Dose taken for 08:30", "Dose taken with no dose time"}
    assert doses["Dose taken for 08:30"].onset == pytest.approx(14.75, abs=ONSET_LIMIT)
    assert doses["Dose taken with no dose time"].onset == pytest.approx(15.75, abs=ONSET_LIMIT)
    assert all(a.duration is None for a in doses.values())


def test_15_faces_and_answers(caplog: pytest.LogCaptureFixture, tmp_path: Path, made: list[str]) -> None:
    at = first_t_index(made) + 1
    faces = [f"F,{k * US},{k - 1}" for k in range(1, 6)]
    result = export_main(caplog, save_recording(tmp_path, "f.txt.gz", [*made[:at], *faces, *made[at:]]),
                         tmp_path / "D")
    assert result.code == 0, result.log
    edf = edfio.read_edf(tmp_path / "D" / f"f_{rm.BOOT_ID}.edf")
    found = [(a.text, a.onset, a.duration) for a in edf.annotations if a.text.startswith("Face")]
    names = ["Tremor Detected", "Rest", "Arm moving", "Waiting", "Dose due"]
    assert [t for t, _, _ in found] == [f"Face {n}" for n in names]
    assert [o for _, o, _ in found] == pytest.approx([0.75, 1.75, 2.75, 3.75, 4.75], abs=ONSET_LIMIT)
    assert all(d is None for _, _, d in found)

    answers = ["W,0,3,0,0.5,10,5", "W,0,4,1,0.5,10,5", "W,0,5,2,0.5,10,5", "W,0,6,3,0.5,10,5",
               "W,0,7,4,0.5,10,5", "W,0,,4,,,", "W,9,2,0,0.5,10,5"]
    result = export_main(caplog, save_recording(tmp_path, "w.txt.gz", [*made[:at], *answers, *made[at:]]),
                         tmp_path / "D")
    assert result.code == 0, result.log
    edf = edfio.read_edf(tmp_path / "D" / f"w_{rm.BOOT_ID}.edf")
    found = [(a.text, a.onset, a.duration) for a in edf.annotations if a.text.startswith("Answer")]
    assert [t for t, _, _ in found] == ["Answer tremor", "Answer no tremor", "Answer arm moving", "Answer warming up"]
    assert [o for _, o, _ in found] == pytest.approx([3, 4, 5, 6], abs=ONSET_LIMIT)
    assert all(d == 4.0 for _, _, d in found)
    assert re.search(r"sensor faults 2\b", result.log)
    assert re.search(r"windows not placed 1\b", result.log)
    assert re.search(r"stretch 9\b", result.log)


def test_16_clipped_samples(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    lines = rm.recording_lines(30, 1500)
    result = export_main(caplog, save_recording(tmp_path, "c.txt.gz", lines), tmp_path / "D")
    assert result.code == 0, result.log
    x = replay_of(lines, tmp_path).axes(rm.BOOT_ID)
    steps = np.rint(32 * x)
    clipped = int(np.count_nonzero((steps < DIGITAL_MIN) | (steps > DIGITAL_MAX)))
    assert clipped > 0
    found = re.search(r"clipped samples (\d+)", result.log)
    assert found is not None and int(found.group(1)) == clipped
    edf = edfio.read_edf(tmp_path / "D" / f"c_{rm.BOOT_ID}.edf")
    for axis, s in enumerate(edf.signals):
        assert np.array_equal(s.digital, digital_of(x[:, axis]))
        assert s.digital.min() >= DIGITAL_MIN and s.digital.max() <= DIGITAL_MAX


def test_17_boot_comes_back(caplog: pytest.LogCaptureFixture, tmp_path: Path, made: list[str]) -> None:
    lines = [*made, *rm.recording_lines(12, 0, boot_id=7), made[0]]
    result = export_main(caplog, save_recording(tmp_path, "m.txt.gz", lines), tmp_path / "D")
    assert result.code == 1
    assert files_in(tmp_path / "D") == []
    assert re.search(rf"boot {rm.BOOT_ID} comes back after boot 7\b", result.log)


# The cases on bad input and on the options.


def test_18_bad_files(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    out = tmp_path / "D"
    missing = tmp_path / "none.txt.gz"
    result = export_main(caplog, missing, out)
    assert result.code == 1 and str(missing) in result.log
    bad = tmp_path / "bad.gz"
    bad.write_text("hello")
    result = export_main(caplog, bad, out)
    assert result.code == 1 and "not a gzip file" in result.log
    empty = tmp_path / "empty.txt.gz"
    empty.write_bytes(gzip.compress(b""))
    result = export_main(caplog, empty, out)
    assert result.code == 1 and "holds no B line" in result.log
    no_boot = save_recording(tmp_path, "no_boot.txt.gz", ["> RESET", "R,0,1,2,3,4,5,6"])
    result = export_main(caplog, no_boot, out)
    assert result.code == 1 and "holds no B line" in result.log
    assert files_in(out) == []


def test_19_cut_short(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    data = (FIRMWARE_LOGS / "record_log.txt.gz").read_bytes()
    half = tmp_path / "half.txt.gz"
    half.write_bytes(data[: len(data) // 2])
    result = export_main(caplog, half, tmp_path / "D")
    assert result.code == 0, result.log
    assert "cut short" in result.log
    text = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(data[: len(data) // 2])
    before = [LAPTOP_TIME.sub("", line) for line in text[: text.rindex(b"\n")].decode().splitlines()]
    samples = len(replay_of(before, tmp_path).samples)
    edf = edfio.read_edf(tmp_path / "D" / "half_2274443476.edf")
    assert edf.num_data_records == samples // 100


def test_20_refuses_existing_file(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    out = tmp_path / "D"
    out.mkdir()
    kept = out / "command_log_505078862.edf"
    kept.write_text("keep")
    result = export_main(caplog, RECORDINGS["command_log"], out)
    assert result.code == 1
    assert str(kept) in result.log
    assert kept.read_text() == "keep"
    assert not (out / "command_log_3162426297.edf").exists()


def test_21_boot_option(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    result = export_main(caplog, RECORDINGS["command_log"], tmp_path / "D", "--boot", "505078862")
    assert result.code == 0, result.log
    assert files_in(tmp_path / "D") == ["command_log_505078862.edf"]
    result = export_main(caplog, RECORDINGS["command_log"], tmp_path / "E", "--boot", "1")
    assert result.code == 1
    assert "3162426297" in result.log and "505078862" in result.log
    result = export_main(caplog, SYNTHETIC, tmp_path / "F", "--boot", "4294967295")
    assert result.code == 1
    assert "has no samples" in result.log
    assert files_in(tmp_path / "E") == [] and files_in(tmp_path / "F") == []


def test_22_replay_missing(caplog: pytest.LogCaptureFixture, tmp_path: Path) -> None:
    out = tmp_path / "D"
    result = export_main(caplog, RECORDINGS["drop_log"], out, "--replay", str(out / "none"))
    assert result.code == 1
    assert f"replay is not at {out / 'none'}" in result.log


# The cases of tools/edfplus.py.


def test_23_seconds_text() -> None:
    assert edfplus.seconds_text(0, signed=True) == "+0"
    assert edfplus.seconds_text(3000000, signed=True) == "+3"
    assert edfplus.seconds_text(12345678, signed=True) == "+12.345678"
    assert edfplus.seconds_text(-250000, signed=True) == "-0.25"
    assert edfplus.seconds_text(1, signed=True) == "+0.000001"
    assert edfplus.seconds_text(4000000, signed=False) == "4"


def test_24_tals() -> None:
    assert edfplus.timekeeping_tal(0) == b"+0\x14\x14\x00"
    assert edfplus.tal_bytes(5250000, 4000000, ["Answer tremor"]) == b"+5.25\x154\x14Answer tremor\x14\x00"
    assert b"\x15" not in edfplus.tal_bytes(19750000, None, ["Dose taken with no dose time"])
    with pytest.raises(edfplus.EdfError):
        edfplus.tal_bytes(0, None, ["a\x14b"])


def test_25_fields() -> None:
    assert edfplus.field("abc", 8) == b"abc     "
    with pytest.raises(edfplus.EdfError):
        edfplus.field("abcdefghi", 8)
    with pytest.raises(edfplus.EdfError):
        edfplus.field("é", 8)


def test_26_record_onsets() -> None:
    with pytest.raises(edfplus.EdfError):
        edfplus.check_record_onsets(np.array([0, 1000000, 1500000]), 1000000)
    assert edfplus.is_continuous(np.array([0, 1000000, 2000000]), 1000000) is True
    assert edfplus.is_continuous(np.array([0, 1000000, 3000000]), 1000000) is False
