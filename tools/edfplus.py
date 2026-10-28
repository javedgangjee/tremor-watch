"""Write EDF+ files with the standard library and numpy.

The bytes follow the EDF+ specification at https://www.edfplus.info. This
module knows the format only. The caller gives the header values, the signal
descriptions, the digital samples as int16, the start of each data record,
and the annotations. Every time is a whole number of microseconds from the
file's start, so no float ever rounds a time.

A file holds the caller's signals and then one "EDF Annotations" signal. Each
data record's annotation signal starts with its time-keeping TAL, which gives
the record's start, so a file with gaps between its records is written as
EDF+D.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path

import numpy as np

US_PER_SECOND = 1_000_000

# The bytes that separate the parts of a TAL.
TAL_END = b"\x00"
DURATION_MARK = b"\x15"
TEXT_END = b"\x14"
FORBIDDEN_TEXT_BYTES = frozenset(b"\x00\x14\x15")

PRINTABLE_LOW = 32
PRINTABLE_HIGH = 126

MAIN_HEADER_BYTES = 256
SIGNAL_HEADER_BYTES = 256
BYTES_PER_SAMPLE = 2

# The EDF dates hold two digits for the year. Years 1985 to 2084 fit, and
# a later year is written as the text "yy", as the EDF+ specification asks.
FIRST_YEAR = 1985
LAST_TWO_DIGIT_YEAR = 2084
CLIPPING_DATE = date(FIRST_YEAR, 1, 1)
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


class EdfError(ValueError):
    """A value that the EDF+ format cannot hold."""


@dataclass(frozen=True)
class SignalSpec:
    """The header fields of one ordinary signal.

    The physical and digital limits are text, so a value such as 1023.875 is
    written exactly as given.
    """

    label: str
    transducer: str
    unit: str
    physical_min: str
    physical_max: str
    digital_min: str
    digital_max: str
    prefiltering: str
    samples_per_record: int


@dataclass(frozen=True)
class Annotation:
    """One annotation, with its onset in microseconds from the file's start."""

    onset_us: int
    duration_us: int | None
    text: str


@dataclass(frozen=True)
class EdfHeader:
    """The main header's values. A start date of None means the date is not known."""

    patient: str
    recording: str
    start_date: date | None
    start_time: time | None
    record_seconds: int


ANNOTATION_SIGNAL = SignalSpec(
    label="EDF Annotations",
    transducer="",
    unit="",
    physical_min="-1",
    physical_max="1",
    digital_min="-32768",
    digital_max="32767",
    prefiltering="",
    samples_per_record=0,
)


def seconds_text(us: int, signed: bool) -> str:
    """Give a time in seconds as decimal text with up to 6 decimals and no trailing zeros.

    With signed, the text starts with + or -, as a TAL onset must.
    """
    if not signed and us < 0:
        raise EdfError(f"a duration of {us} microseconds is negative")
    whole, fraction = divmod(abs(us), US_PER_SECOND)
    text = str(whole)
    if fraction:
        text += "." + f"{fraction:06d}".rstrip("0")
    if us < 0:
        return "-" + text
    return "+" + text if signed else text


def text_bytes(text: str) -> bytes:
    """Give an annotation text as UTF-8, and refuse the bytes that end TAL parts."""
    data = text.encode("utf-8")
    if FORBIDDEN_TEXT_BYTES & set(data):
        raise EdfError(f"the annotation text {text!r} holds byte 0, 20, or 21")
    return data


def tal_bytes(onset_us: int, duration_us: int | None, texts: Sequence[str]) -> bytes:
    """Give one TAL: the onset, the duration when there is one, and each text."""
    out = seconds_text(onset_us, signed=True).encode("ascii")
    if duration_us is not None:
        out += DURATION_MARK + seconds_text(duration_us, signed=False).encode("ascii")
    out += TEXT_END
    for text in texts:
        out += text_bytes(text) + TEXT_END
    return out + TAL_END


def timekeeping_tal(onset_us: int) -> bytes:
    """Give the time-keeping TAL that starts each data record's annotation signal."""
    return tal_bytes(onset_us, None, [""])


def field(value: str, width: int) -> bytes:
    """Give one header field as printable ASCII, left aligned and padded with spaces."""
    if len(value) > width:
        raise EdfError(f"{value!r} does not fit a header field of {width} characters")
    if any(not PRINTABLE_LOW <= ord(c) <= PRINTABLE_HIGH for c in value):
        raise EdfError(f"{value!r} holds a character outside printable ASCII")
    return value.encode("ascii").ljust(width, b" ")


def plus_date_text(day: date | None) -> str:
    """Give a date as the EDF+ subfields write it, as in 23-OCT-2026, or X when it is not known."""
    if day is None:
        return "X"
    return f"{day.day:02d}-{MONTHS[day.month - 1]}-{day.year:04d}"


def startdate_text(day: date | None) -> str:
    """Give the header's startdate field as dd.mm.yy.

    An unknown date gives 01.01.85, and a year after 2084 gives yy.
    """
    day = CLIPPING_DATE if day is None else day
    if day.year < FIRST_YEAR:
        raise EdfError(f"the start date {day} lies before {FIRST_YEAR}, which EDF cannot hold")
    year = "yy" if day.year > LAST_TWO_DIGIT_YEAR else f"{day.year % 100:02d}"
    return f"{day.day:02d}.{day.month:02d}.{year}"


def starttime_text(clock: time | None) -> str:
    """Give the header's starttime field as hh.mm.ss, or 00.00.00 when it is not known."""
    clock = time(0, 0, 0) if clock is None else clock
    return f"{clock.hour:02d}.{clock.minute:02d}.{clock.second:02d}"


def header_bytes(
    header: EdfHeader, signals: Sequence[SignalSpec], annotation_samples: int, records: int, continuous: bool
) -> bytes:
    """Give the main header and one header for each signal, with the annotation signal last."""
    every = [*signals, ANNOTATION_SIGNAL]
    count = len(every)
    samples = [s.samples_per_record for s in signals] + [annotation_samples]
    main = b"".join([
        field("0", 8),
        field(header.patient, 80),
        field(header.recording, 80),
        field(startdate_text(header.start_date), 8),
        field(starttime_text(header.start_time), 8),
        field(str(MAIN_HEADER_BYTES + SIGNAL_HEADER_BYTES * count), 8),
        field("EDF+C" if continuous else "EDF+D", 44),
        field(str(records), 8),
        field(str(header.record_seconds), 8),
        field(str(count), 4),
    ])
    columns = [
        ([s.label for s in every], 16),
        ([s.transducer for s in every], 80),
        ([s.unit for s in every], 8),
        ([s.physical_min for s in every], 8),
        ([s.physical_max for s in every], 8),
        ([s.digital_min for s in every], 8),
        ([s.digital_max for s in every], 8),
        ([s.prefiltering for s in every], 80),
        ([str(n) for n in samples], 8),
        ([""] * count, 32),
    ]
    return main + b"".join(field(value, width) for values, width in columns for value in values)


def check_record_onsets(record_onsets_us: np.ndarray, duration_us: int) -> None:
    """Refuse data records that do not follow each other, at least one duration apart."""
    steps = np.diff(record_onsets_us)
    if np.any(steps < duration_us):
        at = int(np.argmax(steps < duration_us)) + 1
        raise EdfError(
            f"data record {at} starts at {seconds_text(int(record_onsets_us[at]), signed=True)} seconds, "
            f"less than {seconds_text(duration_us, signed=False)} seconds after the record before it"
        )


def is_continuous(record_onsets_us: np.ndarray, duration_us: int) -> bool:
    """Tell whether each data record starts exactly one duration after the one before."""
    return bool(np.all(np.diff(record_onsets_us) == duration_us))


def annotation_block(record_onsets_us: np.ndarray, annotations: Sequence[Annotation]) -> np.ndarray:
    """Give each data record's annotation signal as a row of bytes.

    Each annotation goes in the last record that starts at or before its
    onset, or in the first record when none does. A row holds the record's
    time-keeping TAL and then its annotations in time order, and byte 0 fills
    the rest. The rows have an even width, because each sample holds 2 bytes.
    """
    ordered = sorted(annotations, key=lambda a: a.onset_us)
    onsets = np.array([a.onset_us for a in ordered], dtype=np.int64)
    homes = np.maximum(np.searchsorted(record_onsets_us, onsets, side="right") - 1, 0)
    rows = [bytearray(timekeeping_tal(int(start))) for start in record_onsets_us]
    for home, annotation in zip(homes.tolist(), ordered):
        rows[home] += tal_bytes(annotation.onset_us, annotation.duration_us, [annotation.text])
    width = max(len(row) for row in rows)
    width += width % BYTES_PER_SAMPLE
    block = np.zeros((len(rows), width), dtype=np.uint8)
    for i, row in enumerate(rows):
        block[i, : len(row)] = np.frombuffer(bytes(row), dtype=np.uint8)
    return block


def check_digital(signals: Sequence[SignalSpec], digital: np.ndarray, records: int) -> None:
    """Refuse digital samples whose shape or values do not fit the signal descriptions."""
    if digital.dtype != np.int16:
        raise EdfError(f"the digital samples are {digital.dtype}, not int16")
    if digital.ndim != 3 or digital.shape[:2] != (records, len(signals)):
        raise EdfError(f"the digital samples have shape {digital.shape}, not ({records}, {len(signals)}, n)")
    for i, spec in enumerate(signals):
        if spec.samples_per_record != digital.shape[2]:
            raise EdfError(f"{spec.label} has {spec.samples_per_record} samples a record, not {digital.shape[2]}")
        values = digital[:, i, :]
        if values.size and (values.min() < int(spec.digital_min) or values.max() > int(spec.digital_max)):
            raise EdfError(f"{spec.label} holds a digital value outside {spec.digital_min} to {spec.digital_max}")


def edf_bytes(
    header: EdfHeader,
    signals: Sequence[SignalSpec],
    digital: np.ndarray,
    record_onsets_us: np.ndarray,
    annotations: Sequence[Annotation],
) -> bytes:
    """Give the bytes of a whole EDF+ file.

    digital holds int16 samples of shape (records, signals, samples a record),
    and record_onsets_us gives the start of each data record.
    """
    records = len(record_onsets_us)
    if records == 0:
        raise EdfError("the file has no data record")
    check_digital(signals, digital, records)
    duration_us = header.record_seconds * US_PER_SECOND
    check_record_onsets(record_onsets_us, duration_us)
    block = annotation_block(record_onsets_us, annotations)
    samples = digital.astype("<i2").reshape(records, -1).view(np.uint8)
    head = header_bytes(
        header, signals, block.shape[1] // BYTES_PER_SAMPLE, records, is_continuous(record_onsets_us, duration_us)
    )
    return head + np.concatenate([samples, block], axis=1).tobytes()


def write_new(path: Path, data: bytes) -> None:
    """Write a new file, refuse one that exists, and remove the part file when the write fails."""
    out = path.open("xb")
    try:
        with out:
            out.write(data)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
