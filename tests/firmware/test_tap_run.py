"""Tests for tests/firmware/tap_run.py and the style of the two face scripts.

Each case writes a made-up gzip log of every step of check 13 of
specs/features/11-watch-face/validation.md and judges it with --log-only, so
no watch is needed. The dose clock makes watch time 120 seconds 10:00:00 on
23 October 2026, and the dose minute is 10:02. The judge runs replay, so the
laptop build must exist. They run in the reference venv with this command.

    reference/.venv/bin/python -m pytest tests/firmware -q
"""
from __future__ import annotations

import ast
import gzip
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
TAP_RUN = HERE / "tap_run.py"
FACE_RUN = HERE / "face_run.py"
SCRIPTS = (FACE_RUN, TAP_RUN)
TEST_FILES = (HERE / "test_face_run.py", HERE / "test_tap_run.py")

S = 1_000_000
# O is local midnight at the start of 23 October 2026 in microseconds since 1970.
O = 1_792_713_600_000_000
T6 = 120 * S
OFFSET_US = O + 10 * 3600 * S - T6
MINUTE = 10 * 60 + 2
DOSE_LOCAL = O + MINUTE * 60 * S
T_DUE = DOSE_LOCAL - OFFSET_US
# The laptop's clock runs this many seconds ahead of the watch's.
LAPTOP_AHEAD = 5.0

CHANGES = (
    "upper_accepted",
    "upper_dose",
    "two_d_lines",
    "double_tap_accepted",
    "logged_long",
    "dose_off_minute",
    "no_face_back",
    "idle_short",
    "tone_after_tap",
)


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


def view(at: int, screen: str, face: int = 1, due: int = 0) -> str:
    """Give a SCREEN_VIEW line."""
    look = {1: "fill colour=2a7242", 4: "fill colour=3f2559"}[face]
    return (f"SCREEN_VIEW at_us={at} screen={screen} face={face} circle={look} time=10:00 due={due} "
            f"next=10:02 last_tremor=none share=0 blocks=1 hollow=1")


def touch(at: int, screen: str, target: str, accepted: int, y: int = 400) -> str:
    """Give a TOUCH line."""
    return f"TOUCH at_us={at} x=205 y={y} screen={screen} target={target} accepted={accepted}"


def settings(source: str, tone: int, times: str, name: str) -> str:
    """Give a SETTINGS line."""
    return f"SETTINGS source={source} store=ok tone={tone} times={times} name={name}"


class Log:
    """A made-up log in the making, with the watch time of each line."""

    def __init__(self) -> None:
        self.lines: list[tuple[int, str]] = []

    def add(self, at: int, text: str) -> None:
        """Add one line at a watch time."""
        self.lines.append((at, text))

    def command(self, at: int, text: str, answer: str, between: list[str]) -> None:
        """Add a command, the lines that answer it, and its A line."""
        self.add(at, f"> {text}")
        for n, line in enumerate(between):
            self.add(at + 1000 + n, line)
        self.add(at + 2000 + len(between), answer)


def tap_took_it(log: Log, at: int, count: int, answered: str, local: int) -> None:
    """Add an accepted "Took it" tap with its tone and its dose lines."""
    log.add(at, touch(at, "medication", "took_it", 1))
    log.add(at + 30_000, f"TONE_PLAY at_us={at + 30_000} kind=tap tones=1")
    log.add(at + 40_000, f"DOSE at_us={at} answers_local_us={local} count={count}")
    log.add(at + 40_001, f"D,{at},{answered}")


def make_log(change: str | None = None) -> list[tuple[float, str]]:
    """Give a log of every step of check 13, with one change or none."""
    log = Log()
    version = load("record_run", HERE / "record_run.py").FIRMWARE_VERSION
    log.add(1 * S, f"B,305419896,11,{version},{table_hash()}")
    log.add(1 * S + 1, "S,0,0,233166,114330200,1024")
    stamp = 2 * S
    log.add(stamp, f"T,100,11,{stamp}")
    for i in range(11):
        log.add(stamp + 1 + i, f"R,{100 + i},3,-5,2,-146,-24,-3773")
    log.command(3 * S, "TONE,1", "A,4,0", [settings("command", 1, "none", "")])
    log.command(4 * S, f"CLOCK,1792749480000000,60", "A,1,0",
                [f"CLOCK at_us={4 * S} offset_us={OFFSET_US} local_us={4 * S + OFFSET_US}"])

    t1 = 20 * S
    log.add(t1 - 1, "> STEP 1")
    log.add(t1, touch(t1, "home", "home", 1))
    log.add(t1 + 20_000, f"TONE_PLAY at_us={t1 + 20_000} kind=tap tones=1")
    log.add(t1 + 300_000, view(t1 + 300_000, "medication"))

    t2 = 23 * S
    log.add(t2 - 1, "> STEP 2")
    log.add(t2, touch(t2, "medication", "home" if change == "upper_accepted" else "none",
                      1 if change == "upper_accepted" else 0, y=100))
    if change == "upper_dose":
        log.add(t2 + 40_000, f"DOSE at_us={t2} answers_local_us=-1 count=1")

    t3 = 26 * S
    log.add(t3 - 1, "> STEP 3")
    tap_took_it(log, t3, 1, "", -1)
    log.add(t3 + 320_000, view(t3 + 320_000, "logged"))
    home_after = 3_500_000 if change == "logged_long" else 3_000_000
    log.add(t3 + 320_000 + home_after, view(t3 + 320_000 + home_after, "home"))

    t4 = 32 * S
    log.add(t4 - 1, "> STEP 4")
    log.add(t4, touch(t4, "home", "home", 1))
    log.add(t4 + 20_000, f"TONE_PLAY at_us={t4 + 20_000} kind=tap tones=1")
    log.add(t4 + 300_000, view(t4 + 300_000, "medication"))
    second = 1 if change == "double_tap_accepted" else 0
    log.add(t4 + 400_000, touch(t4 + 400_000, "medication", "took_it", second))

    t5 = 36 * S
    log.add(t5 - 1, "> STEP 5")
    tap_took_it(log, t5, 2, "", -1)
    log.add(t5 + 330_000, view(t5 + 330_000, "logged"))
    log.add(t5 + 400_000, touch(t5 + 400_000, "logged", "none", 0))
    if change == "two_d_lines":
        log.add(t5 + 400_001, f"D,{t5 + 400_000},")
    log.add(t5 + 3_330_000, view(t5 + 3_330_000, "home"))

    log.add(T6 - 1, "> STEP 6")
    log.command(T6, f"SCHEDULE,TapTest,{MINUTE}", "A,2,0", [settings("command", 1, str(MINUTE), "TapTest")])
    log.add(T6 + 10_000, view(T6 + 10_000, "home"))
    due = T_DUE + 400_000
    log.add(due, "TONE enabled=1")
    log.add(due + 1, f"FACE at_us={due} state=4")
    log.add(due + 2, f"F,{due},4")
    log.add(due + 20_000, view(due + 20_000, "home", face=4, due=1))
    log.add(due + 60_000, f"TONE_PLAY at_us={due + 60_000} kind=dose tones=3")
    press = due + 20 * S
    log.add(press, f"BUTTON at_us={press} screen=medication")
    log.add(press + 20_000, view(press + 20_000, "medication", face=4, due=1))
    tap = press + 3 * S
    answered = DOSE_LOCAL + (60 * S if change == "dose_off_minute" else 0)
    tap_took_it(log, tap, 3, str(answered), answered)
    if change != "no_face_back":
        log.add(tap + 41_000, f"FACE at_us={tap + 41_000} state=1")
        log.add(tap + 41_001, f"F,{tap + 41_000},1")
    log.add(tap + 60_000, view(tap + 60_000, "medication"))
    log.add(tap + 330_000, view(tap + 330_000, "logged"))
    log.add(tap + 3_330_000, view(tap + 3_330_000, "home"))

    t7 = tap + 10 * S
    log.add(t7 - 1, "> STEP 7")
    for n, screen in enumerate(("medication", "session", "status", "home")):
        at = t7 + n * S
        log.add(at, f"BUTTON at_us={at} screen={screen}")
        log.add(at + 20_000, view(at + 20_000, screen))

    t8 = t7 + 10 * S
    log.add(t8 - 1, "> STEP 8")
    for n, screen in enumerate(("medication", "session")):
        at = t8 + n * S
        log.add(at, f"BUTTON at_us={at} screen={screen}")
        log.add(at + 20_000, view(at + 20_000, screen))
    back = t8 + S + (290 if change == "idle_short" else 300) * S
    log.add(back, view(back, "home"))

    t9 = back + 10 * S
    log.add(t9 - 1, "> STEP 9")
    log.command(t9, "TONE,0", "A,4,0", [settings("command", 0, str(MINUTE), "TapTest")])
    tap9 = t9 + 2 * S
    log.add(tap9, touch(tap9, "home", "home", 1))
    if change == "tone_after_tap":
        log.add(tap9 + 30_000, f"TONE_PLAY at_us={tap9 + 30_000} kind=tap tones=1")
    log.add(tap9 + 300_000, view(tap9 + 300_000, "medication"))
    end = tap9 + 5 * S
    log.command(end, "TONE,1", "A,4,0", [settings("command", 1, str(MINUTE), "TapTest")])
    log.command(end + S, "SCHEDULE", "A,2,0", [settings("command", 1, "none", "")])
    log.command(end + 2 * S, "TONE,1", "A,4,0", [settings("command", 1, "none", "")])

    ordered = sorted(enumerate(log.lines), key=lambda e: (e[1][0], e[0]))
    return [(at / S + LAPTOP_AHEAD, text) for _, (at, text) in ordered]


def judge(tmp_path: Path, lines: list[tuple[float, str]]) -> int:
    """Write the log and run the judge on it."""
    log = tmp_path / "tap_log.txt.gz"
    report = tmp_path / "tap_report.md"
    with gzip.open(log, "wt") as out:
        for seconds, text in lines:
            out.write(f"{seconds:.3f}\t{text}\n")
    return load("tap_run", TAP_RUN).main(["--log-only", "--log", str(log), "--report", str(report)])


def test_clean_log(tmp_path: Path) -> None:
    """Case 53: the clean log of every step passes."""
    assert judge(tmp_path, make_log()) == 0


def test_changed_logs(tmp_path: Path) -> None:
    """Case 54: each of the nine changed copies fails."""
    for change in CHANGES:
        folder = tmp_path / change
        folder.mkdir()
        assert judge(folder, make_log(change)) == 1, change


def functions_of(path: Path) -> list[ast.FunctionDef]:
    """Give every function in a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def test_style() -> None:
    """Case 55: type hints everywhere, one prompt function with print, no os.path,
    no except Exception, and no line that starts with import serial."""
    for path in SCRIPTS + TEST_FILES:
        for fn in functions_of(path):
            args = fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs
            # A method's self is not given a type hint.
            for arg in [a for a in args if a.arg not in ("self", "cls")]:
                assert arg.annotation is not None, f"{path.name}: {fn.name}({arg.arg}) has no type hint"
            assert fn.returns is not None, f"{path.name}: {fn.name} has no return hint"
    for path in SCRIPTS:
        source = path.read_text(encoding="utf-8")
        assert "os.path" not in source, path.name
        assert "except Exception" not in source, path.name
        assert not any(line.startswith("import serial") for line in source.splitlines()), path.name
    assert "print(" not in FACE_RUN.read_text(encoding="utf-8")
    printers = [fn.name for fn in functions_of(TAP_RUN) if "print(" in ast.get_source_segment(
        TAP_RUN.read_text(encoding="utf-8"), fn) or ""]
    assert TAP_RUN.read_text(encoding="utf-8").count("print(") == 1
    assert printers == ["prompt"]
