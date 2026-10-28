"""Tests for tests/firmware/face_run.py.

Each case writes a made-up gzip log of every step of face_run.py and judges
it with --log-only, so no watch is needed. The watch's clock is set at
watch time 20 seconds to 16:56:30 local time on 23 October 2026. The first
dose is at 16:59, and the second at 17:16. They run in the reference venv
with this command.

    reference/.venv/bin/python -m pytest tests/firmware -q
"""
from __future__ import annotations

import gzip
import importlib.util
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
FACE_RUN = HERE / "face_run.py"

SECOND = 1_000_000
MINUTE = 60 * SECOND
DAY = 1440 * MINUTE
# Local midnight at the start of 23 October 2026 in microseconds since 1970.
MIDNIGHT = 1_792_713_600_000_000
CLOCK_AT = 20 * SECOND
OFFSET_US = MIDNIGHT + (16 * 60 + 56) * MINUTE + 30 * SECOND - CLOCK_AT
DOSE_1 = 16 * 60 + 59
DOSE_2 = 17 * 60 + 16
T0 = 235_000
FACE_AT = 10_300_000
END_US = (17 * 60 + 17) * MINUTE + MIDNIGHT - OFFSET_US
BOOT_SETTINGS = "SETTINGS source=boot store=ok tone=1 times=none name="
LAPTOP_LAG_S = 0.3


def load(name: str, path: Path) -> ModuleType:
    """Import a module from its path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The dataclasses in the module look it up by name.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def table_hash() -> str:
    """Read DET_MODEL_SHA256 from core/detector_tables.h."""
    text = (HERE.parents[1] / "core" / "detector_tables.h").read_text()
    match = re.search(r'^#define DET_MODEL_SHA256 "([0-9a-f]{64})"', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


def watch_at(local_minute: int) -> int:
    """Give the watch time of a local minute of 23 October."""
    return MIDNIGHT + local_minute * MINUTE - OFFSET_US


def hh_mm(local_minute: int) -> str:
    """Give a minute of the day as HH:MM."""
    return f"{local_minute // 60 % 24:02d}:{local_minute % 60:02d}"


@dataclass
class Fields:
    """The fields of the SCREEN_VIEW line."""

    screen: str = "home"
    face: int = 3
    time: str = "--:--"
    due: int = 0
    next: str = "none"
    last_tremor: str = "none"
    share: int = -1
    blocks: int = 0
    hollow: str = "none"


LOOKS = {0: ("fill", "1b2e42"), 1: ("outline", "26292b"), 2: ("fill", "2a7242"), 3: ("outline", "5c6265"),
         4: ("fill", "3f2559")}
# The looks of version 11 before commit 7f6b90e, with Rest and Arm moving the other way round.
FIRST_LOOKS = {**LOOKS, 1: ("fill", "2a7242"), 2: ("outline", "26292b")}


@dataclass
class Maker:
    """Builds the watch's lines in order of watch time."""

    lines: list[tuple[float, str]] = field(default_factory=list)
    view: Fields = field(default_factory=Fields)
    clock_set: bool = False
    looks: dict[int, tuple[str, str]] = field(default_factory=lambda: dict(LOOKS))

    def add(self, at: int, text: str) -> None:
        """Add one watch line that arrives on the laptop a little after its watch time."""
        self.lines.append((at / SECOND + LAPTOP_LAG_S, text))

    def script(self, at: int, text: str) -> None:
        """Add one of the script's own lines at a watch time."""
        self.lines.append((at / SECOND + LAPTOP_LAG_S - 0.01, f"> {text}"))

    def show(self, at: int, **changes: object) -> None:
        """Change the view's fields and add a SCREEN_VIEW line when one changed."""
        before = Fields(**vars(self.view))
        for key, value in changes.items():
            setattr(self.view, key, value)
        if vars(before) == vars(self.view) and self.lines and "SCREEN_VIEW" in "".join(t for _, t in self.lines):
            return
        v = self.view
        circle, colour = self.looks[v.face]
        self.add(at, f"SCREEN_VIEW at_us={at} screen={v.screen} face={v.face} circle={circle} colour={colour} "
                     f"time={v.time} due={v.due} next={v.next} last_tremor={v.last_tremor} share={v.share} "
                     f"blocks={v.blocks} hollow={v.hollow}")

    def face(self, at: int, state: int) -> None:
        """Add a FACE line, its F line, and the view."""
        self.add(at, f"FACE at_us={at} state={state}")
        self.add(at, f"F,{at},{state}")
        self.show(at + 15_000, face=state)


def window_time(n: int) -> int:
    """Give the watch time of window n of stretch 0."""
    return T0 + 10_000 * (100 * n + 399)


def make_lines(looks: dict[int, tuple[str, str]] | None = None, version: int | None = None) -> list[tuple[float, str]]:
    """Give every line of a clean run in order of laptop time, with the looks and the version of the firmware
    now or others."""
    if version is None:
        version = load("record_run", HERE / "record_run.py").FIRMWARE_VERSION
    m = Maker(looks=dict(looks or LOOKS))
    m.lines.append((0.0, "> RESET"))
    m.lines.append((0.05, "ESP-ROM:esp32s3-20210327"))
    m.add(60_000, f"B,305419896,11,{version},{table_hash()}")
    m.add(61_000, "START uptime_us=61335")
    m.add(62_000, BOOT_SETTINGS)
    m.add(T0, f"S,0,0,{T0},0,1024")
    m.add(580_000, "SCREEN_START at_us=580000 display=ok touch=ok audio=ok button=ok face=ok internal_free=162959 "
                   "internal_largest=90112")
    m.show(680_000)

    events: list[tuple[int, Callable[[], None]]] = []

    # The answers: window 0 warms up, window 8 is tremor, and the others are no tremor.
    counts = {"tremor": 0, "still": 0}
    blocks: dict[int, int] = {}

    def answer(n: int) -> Callable[[], None]:
        def run() -> None:
            at = window_time(n) + 100_000
            code = 3 if n == 0 else 0 if n == 8 else 1
            m.add(at, f"W,0,{n},{code},0.0001,0.5,7.5")
            if n > 0 and n % 4 == 0:
                counts["still"] += 1
                counts["tremor"] += 1 if code == 0 else 0
                b = window_time(n) // (10 * MINUTE)
                for k in range(max(blocks, default=-1) + 1, b + 1):
                    blocks[k] = 0
                blocks[b] += 1
                share = (200 * counts["tremor"] // counts["still"] + 1) // 2
                hollow = "".join("1" if blocks[k] < 30 else "0" for k in sorted(blocks))
                m.show(at + 10_000, share=share, blocks=len(blocks), hollow=hollow)
        return run

    n = 0
    while window_time(n) + 100_000 < END_US:
        events.append((window_time(n) + 100_000, answer(n)))
        n += 1
    events.append((FACE_AT, lambda: m.face(FACE_AT, 1)))

    def minutes() -> None:
        for minute in range(1, END_US // MINUTE + 1):
            at = minute * MINUTE
            events.append((at + 500, lambda at=at, minute=minute: (
                m.add(at + 500, f"SCREEN_MINUTE minute={minute} updates={60 * minute} face=1 face_changes=1 "
                                f"views=9 taps=0 tones=1 stack_free=2312 internal_min=47972 width_mismatch=0 "
                                f"took_it_drops=0"),
                m.add(at + 600, f"STATE_MINUTE minute={minute} answers={60 * minute} screen_drops=0 "
                                f"stack_free=2220 battery=0 battery_mv=0 battery_percent=-1 took_it=0 refused=0"),
                m.add(at + 700, f"USB_MINUTE minute={minute} line_drops=0 port_drops=0 restarts=0 bytes=1 "
                                f"commands=0 bad_commands=0 stack_free=2684"),
            )))

    minutes()

    def clock_minutes() -> None:
        first = (CLOCK_AT + OFFSET_US - MIDNIGHT) // MINUTE + 1
        for local in range(first, (END_US + OFFSET_US - MIDNIGHT) // MINUTE + 1):
            at = watch_at(local)
            events.append((at + 200_000, lambda at=at, local=local: m.show(at + 200_000, time=hh_mm(local))))

    clock_minutes()

    def command(at: int, text: str, between: list[str], answer_text: str, after: Callable[[], None]) -> None:
        def run() -> None:
            m.script(at, text)
            for i, line in enumerate(between):
                m.add(at + 1_000 + i, line)
            m.add(at + 2_000, answer_text)
            after()
        events.append((at, run))

    command(15 * SECOND, "TONE,1", ["SETTINGS source=command store=ok tone=1 times=none name="], "A,4,0",
            lambda: None)
    command(CLOCK_AT, f"CLOCK,{OFFSET_US + CLOCK_AT - 60 * MINUTE},60",
            [f"CLOCK at_us={CLOCK_AT} offset_us={OFFSET_US} local_us={CLOCK_AT + OFFSET_US}"], "A,1,0",
            lambda: m.show(CLOCK_AT + 3_000, time="16:56"))
    sched_1 = 21 * SECOND
    command(sched_1, f"SCHEDULE,FaceTest,{DOSE_1}",
            [f"SETTINGS source=command store=ok tone=1 times={DOSE_1} name=FaceTest"], "A,2,0",
            lambda: m.show(sched_1 + 3_000, next=hh_mm(DOSE_1)))

    t1 = watch_at(DOSE_1) + 400_000

    def due_1() -> None:
        m.add(t1 - 10, "TONE enabled=1")
        m.add(t1, f"FACE at_us={t1} state=4")
        m.add(t1, f"F,{t1},4")
        m.show(t1 + 15_000, face=4, due=1)
        m.add(t1 + 50_000, f"TONE_PLAY at_us={t1 + 50_000} kind=dose tones=3")

    events.append((t1, due_1))
    end_1 = t1 + 900 * SECOND

    def end_due_1() -> None:
        m.add(end_1, f"FACE at_us={end_1} state=1")
        m.add(end_1, f"F,{end_1},1")
        m.show(end_1 + 15_000, face=1, due=0)

    events.append((end_1, end_due_1))
    tone_off = end_1 + 12 * SECOND
    command(tone_off, "TONE,0", [f"SETTINGS source=command store=ok tone=0 times={DOSE_1} name=FaceTest"], "A,4,0",
            lambda: None)
    sched_2 = tone_off + SECOND
    command(sched_2, f"SCHEDULE,FaceTest,{DOSE_2}",
            [f"SETTINGS source=command store=ok tone=0 times={DOSE_2} name=FaceTest"], "A,2,0",
            lambda: m.show(sched_2 + 3_000, next=hh_mm(DOSE_2)))
    t2 = watch_at(DOSE_2) + 400_000

    def due_2() -> None:
        m.add(t2 - 10, "TONE enabled=0")
        m.add(t2, f"FACE at_us={t2} state=4")
        m.add(t2, f"F,{t2},4")
        m.show(t2 + 15_000, face=4, due=1)

    events.append((t2, due_2))
    session = t2 + 12 * SECOND

    def session_lines() -> None:
        m.script(session, "SESSION")
        m.add(session + 1_000, f"SESSION at_us={session + 1_000} changed=1")
        m.add(session + 1_001, f"FACE at_us={session + 1_001} state=3")
        m.add(session + 1_001, f"F,{session + 1_001},3")
        m.add(session + 2_000, "A,3,0")
        m.show(session + 20_000, face=3, due=0, share=-1, blocks=0, hollow="none")

    events.append((session, session_lines))
    command(session + 6 * SECOND, "SCHEDULE", ["SETTINGS source=command store=ok tone=0 times=none name="],
            "A,2,0", lambda: m.show(session + 6 * SECOND + 3_000, next="none"))
    command(session + 7 * SECOND, "TONE,1", ["SETTINGS source=command store=ok tone=1 times=none name="],
            "A,4,0", lambda: None)

    for _, run in sorted(events, key=lambda e: e[0]):
        run()
    return sorted(m.lines, key=lambda e: e[0])


def write_log(path: Path, lines: list[tuple[float, str]]) -> None:
    """Write a gzip log with the laptop's time on each line."""
    with gzip.open(path, "wt") as out:
        for seconds, text in lines:
            out.write(f"{seconds:.3f}\t{text}\n")


def judge(tmp_path: Path, lines: list[tuple[float, str]]) -> int:
    """Write the log and judge it with --log-only."""
    log = tmp_path / "face_log.txt.gz"
    write_log(log, lines)
    return load("face_run", FACE_RUN).main(["--log-only", "--log", str(log), "--report", str(tmp_path / "r.md")])


def index_of(lines: list[tuple[float, str]], test: Callable[[str], bool], start: int = 0) -> int:
    """Give the place of the first line from start that meets the test."""
    return next(i for i in range(start, len(lines)) if test(lines[i][1]))


def replace_field(text: str, key: str, value: str) -> str:
    """Give a diagnostic line with one key=value field changed."""
    return re.sub(rf"\b{key}=\S*", f"{key}={value}", text)


def change(lines: list[tuple[float, str]], i: int, key: str, value: str) -> list[tuple[float, str]]:
    """Give a copy of the lines with one field of line i changed."""
    out = list(lines)
    out[i] = (out[i][0], replace_field(out[i][1], key, value))
    return out


def test_case_50_clean(tmp_path: Path) -> None:
    """The clean log passes."""
    assert judge(tmp_path, make_lines()) == 0


def changed_copies(lines: list[tuple[float, str]]) -> dict[str, list[tuple[float, str]]]:
    """Give the twelve changed copies of the clean log."""
    start = index_of(lines, lambda t: t.startswith("SCREEN_START"))
    clock = index_of(lines, lambda t: t.startswith("> CLOCK"))
    first_view = index_of(lines, lambda t: t.startswith("SCREEN_VIEW"))
    after_clock = index_of(lines, lambda t: t.startswith("SCREEN_VIEW") and "time=--:--" not in t, clock)
    f4 = index_of(lines, lambda t: t.startswith("F,") and t.endswith(",4"))
    v4 = index_of(lines, lambda t: t.startswith("SCREEN_VIEW") and " face=4 " in t, f4)
    first_play = index_of(lines, lambda t: t.startswith("TONE_PLAY"))
    tone_off_line = index_of(lines, lambda t: t == "TONE enabled=0")
    minute = index_of(lines, lambda t: t.startswith("SCREEN_MINUTE"))
    session = index_of(lines, lambda t: t == "> SESSION")
    last_view = max(i for i in range(session) if lines[i][1].startswith("SCREEN_VIEW"))
    hollow = re.search(r"hollow=(\S+)", lines[last_view][1])
    assert hollow is not None and hollow.group(1)[0] == "0"

    off = re.search(r"time=(\d\d):(\d\d)", lines[after_clock][1])
    assert off is not None
    shifted = (int(off.group(1)) * 60 + int(off.group(2)) + 2) % 1440
    no_view = list(lines)
    del no_view[v4]
    no_play = list(lines)
    del no_play[first_play]
    extra_play = list(lines)
    seconds = lines[tone_off_line][0] + 0.05
    extra_play.insert(tone_off_line + 1, (seconds, f"TONE_PLAY at_us={int(seconds * SECOND)} kind=dose tones=3"))
    extra_d = list(lines)
    extra_d.insert(f4 + 1, (lines[f4][0], "D,1000,"))
    return {
        "display": change(lines, start, "display", "error"),
        "internal_free": change(lines, start, "internal_free", "10000"),
        "time before clock": change(lines, first_view, "time", "15:58"),
        "time after clock": change(lines, after_clock, "time", hh_mm(shifted)),
        "no face 4 view": no_view,
        "colour": change(lines, v4, "colour", "6a3d9a"),
        "no tone play": no_play,
        "tone play when off": extra_play,
        "width_mismatch": change(lines, minute, "width_mismatch", "1"),
        "internal_min": change(lines, minute, "internal_min", "9000"),
        "hollow": change(lines, last_view, "hollow", "1" + hollow.group(1)[1:]),
        "D line": extra_d,
    }


def test_case_51_changed_copies(tmp_path: Path) -> None:
    """Each of the twelve changed copies fails."""
    copies = changed_copies(make_lines())
    assert len(copies) == 12
    failed = [name for name, lines in copies.items() if judge(tmp_path, lines) != 1]
    assert failed == []


def test_looks_of_each_version(tmp_path: Path) -> None:
    """A saved log of version 11 may show either set of looks, but not a mix. A log of version 12 and a run
    with the watch need the looks of the firmware now."""
    face_run = load("face_run", FACE_RUN)
    assert face_run.LOOKS == LOOKS
    assert face_run.FIRST_LOOKS == FIRST_LOOKS
    assert [looks for _, looks in face_run.LOOKS_BY_VERSION[11]] == [LOOKS, FIRST_LOOKS]
    assert face_run.look_sets(11, live=True) == [("the looks of the firmware now", LOOKS)]
    record_run = load("record_run", HERE / "record_run.py")
    assert record_run.FIRMWARE_VERSION in face_run.KNOWN_VERSIONS

    assert judge(tmp_path, make_lines(FIRST_LOOKS, version=12)) == 1
    first = make_lines(FIRST_LOOKS, version=11)
    assert judge(tmp_path, first) == 0
    assert "the looks before commit 7f6b90e" in (tmp_path / "r.md").read_text()
    log = face_run.parse([record_run.Entry(t, text) for t, text in first])
    assert face_run.check_faces(log, 11, live=False).passed
    assert not face_run.check_faces(log, 11, live=True).passed

    rest = index_of(first, lambda t: t.startswith("SCREEN_VIEW") and " face=1 " in t)
    mixed = change(change(first, rest, "circle", "outline"), rest, "colour", "26292b")
    assert judge(tmp_path, mixed) == 1


def test_unknown_version_refused(tmp_path: Path) -> None:
    """A saved log of a version with no face is refused, and no report is written."""
    lines = make_lines()
    i = index_of(lines, lambda t: t.startswith("B,"))
    fields = lines[i][1].split(",")
    fields[3] = "9"
    lines[i] = (lines[i][0], ",".join(fields))
    assert judge(tmp_path, lines) == 1
    assert not (tmp_path / "r.md").exists()


def test_case_52_dose_minute() -> None:
    """The dose minute is the next whole minute at least 90 seconds ahead."""
    face_run = load("face_run", FACE_RUN)
    assert face_run.dose_minute(datetime(2026, 10, 23, 16, 58, 30)) == 1020
    assert face_run.dose_minute(datetime(2026, 10, 23, 16, 58, 31)) == 1021
