"""Tests for tools/watch_cli.py.

Cases follow specs/features/10-laptop-tools/validation.md.

They need no watch and no pyserial. A fake port stands in for the watch, and a
fake serial module stands in for pyserial where the tool opens a port. They run
in the reference venv.

    reference/.venv/bin/python -m pytest tests/tools/test_watch_cli.py -q
"""
from __future__ import annotations

import ast
import gzip
import logging
import os
import re
import signal
import sys
import threading
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import watch_cli  # noqa: E402

TOOL = REPO / "tools" / "watch_cli.py"
COMPARE = REPO / "tools" / "compare_session.py"
TYPED_FILES = [
    TOOL,
    COMPARE,
    REPO / "tests" / "replay" / "recording_maker.py",
    REPO / "tests" / "replay" / "test_replay_recording.py",
    REPO / "tests" / "tools" / "test_watch_cli.py",
    REPO / "tests" / "tools" / "test_compare_session.py",
]
HEADER = REPO / "core" / "detector_tables.h"
UTC = timezone.utc


def table_hash() -> str:
    """Give DET_MODEL_SHA256 from core/detector_tables.h."""
    found = re.search(r'#define DET_MODEL_SHA256 "([0-9a-f]{64})"', HEADER.read_text(encoding="utf-8"))
    assert found is not None
    return found.group(1)


class FakePort:
    """A port that gives scripted lines and keeps every write.

    The lines are there from the start. The answers join them at the first
    write, as the watch answers a command only after it arrives. When the lines
    run out, readline() gives b"", or raises KeyboardInterrupt when asked to.
    """

    def __init__(self: FakePort, lines: list[str], answers: list[str] | None = None, interrupt: bool = False) -> None:
        self.waiting = [(text + "\n").encode() for text in lines]
        self.answers = [(text + "\n").encode() for text in answers or []]
        self.interrupt = interrupt
        self.writes: list[bytes] = []
        self.events: list[tuple[str, float, bytes]] = []
        self.closed = False

    def readline(self: FakePort) -> bytes:
        if self.waiting:
            raw = self.waiting.pop(0)
            self.events.append(("read", time.monotonic(), raw))
            return raw
        if self.interrupt:
            raise KeyboardInterrupt
        time.sleep(0.005)
        return b""

    def write(self: FakePort, data: bytes) -> int:
        self.writes.append(data)
        self.events.append(("write", time.monotonic(), data))
        self.waiting.extend(self.answers)
        self.answers = []
        return len(data)

    def close(self: FakePort) -> None:
        self.closed = True


class PortOpener:
    """Stands in for watch_cli.open_port(), handing out fake ports and keeping each call's arguments."""

    def __init__(self: PortOpener, ports: list[FakePort]) -> None:
        self.ports = list(ports)
        self.calls: list[tuple[str, bool]] = []

    def __call__(self: PortOpener, port: str, reset: bool) -> FakePort:
        self.calls.append((port, reset))
        return self.ports.pop(0)


def boot_lines(answer: str) -> list[str]:
    """Give the lines of one boot, with the given answer to the clock command."""
    lines = [
        "ESP-ROM:esp32s3-20210327",
        "T,500,11,123",
        f"B,305419896,11,9,{table_hash()}",
        "S,0,0,250000,0,1024",
        answer,
        "T,0,11,250000",
    ]
    return lines + [f"R,{n},1,2,3,0,0,4096" for n in range(11)]


def saved_entries(path: Path) -> list[tuple[str, str]]:
    """Read back a saved recording as pairs of time text and line text."""
    with gzip.open(path, "rt") as source:
        rows = source.read().splitlines()
    pairs: list[tuple[str, str]] = []
    for row in rows:
        stamp, _, text = row.partition("\t")
        pairs.append((stamp, text))
    return pairs


def test_12_clock_command() -> None:
    now = datetime(2026, 10, 23, 8, 57, 0, tzinfo=UTC)
    assert watch_cli.clock_command(now, timedelta(minutes=60)) == "CLOCK,1792745820000000,60"
    assert watch_cli.clock_command(now, timedelta(minutes=-240)) == "CLOCK,1792745820000000,-240"
    assert watch_cli.clock_command(now, timedelta(hours=5, minutes=30)) == "CLOCK,1792745820000000,330"
    fine = datetime(2026, 10, 23, 8, 57, 0, 123456, tzinfo=UTC)
    assert watch_cli.clock_command(fine, timedelta(minutes=60)) == "CLOCK,1792745820123456,60"


def test_13_schedule_command() -> None:
    sc = watch_cli.schedule_command
    assert sc("Levodopa", ["16:00"]) == "SCHEDULE,Levodopa,960"
    assert sc("Levodopa", ["08:00", "12:00", "20:00"]) == "SCHEDULE,Levodopa,480,720,1200"
    assert sc("Sinemet-CR.25/100+", ["00:00", "23:59"]) == "SCHEDULE,Sinemet-CR.25/100+,0,1439"
    six = ["00:00", "00:01", "00:02", "00:03", "00:04", "00:05"]
    assert sc("Levodopa", six) == "SCHEDULE,Levodopa,0,1,2,3,4,5"
    assert sc("Levodopa", []) == "SCHEDULE,Levodopa"
    assert sc(None, []) == "SCHEDULE"


def test_14_schedule_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ["Levo dopa", "ABCDEFGHIJKLMNOPQRSTU", "Lévodopa", "Levo,dopa"]:
        with pytest.raises(ValueError):
            watch_cli.schedule_command(name, ["08:00"])
    for when in ["24:00", "12:60", "8:00", "8am"]:
        with pytest.raises(ValueError):
            watch_cli.schedule_command("Levodopa", [when])
    seven = ["00:00", "00:01", "00:02", "00:03", "00:04", "00:05", "00:06"]
    with pytest.raises(ValueError):
        watch_cli.schedule_command("Levodopa", seven)
    with pytest.raises(ValueError):
        watch_cli.schedule_command("Levodopa", ["08:00", "08:00"])

    opener = PortOpener([])
    monkeypatch.setattr(watch_cli, "open_port", opener)
    assert watch_cli.main(["schedule", "Levo dopa", "08:00"]) == 2
    assert watch_cli.main(["schedule", "Levodopa", "24:00"]) == 2
    assert opener.calls == []


def test_15_tone_and_session() -> None:
    assert watch_cli.tone_command(True) == "TONE,1"
    assert watch_cli.tone_command(False) == "TONE,0"
    assert watch_cli.session_command() == "SESSION"


def test_16_send_command(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def ports() -> list[FakePort]:
        return [
            FakePort(["R,1,0,0,0,0,0,4096", "A,1,0", "A,4,0"]),
            FakePort([], answers=["A,4,3"]),
            FakePort([], answers=["A,4,5"]),
            FakePort([]),
        ]

    first, second, third, fourth = ports()
    assert watch_cli.send_command(first, "TONE,0") == 0
    assert first.writes == [b"TONE,0\n"]
    assert watch_cli.send_command(second, "TONE,0", first_line_s=0.1) == 3
    assert watch_cli.send_command(third, "TONE,0", first_line_s=0.1) == 5
    assert watch_cli.send_command(fourth, "TONE,0", first_line_s=0.1, answer_s=0.2) is None

    # Shorter waits than main()'s keep the test quick and change nothing else.
    monkeypatch.setattr(watch_cli, "FIRST_LINE_S", 0.1)
    monkeypatch.setattr(watch_cli, "ANSWER_S", 0.2)
    fresh = ports()
    opener = PortOpener(fresh)
    monkeypatch.setattr(watch_cli, "open_port", opener)
    codes: list[int] = []
    busy: list[bool] = []
    for _ in fresh:
        caplog.clear()
        with caplog.at_level(logging.INFO):
            codes.append(watch_cli.main(["tone", "off"]))
        busy.append("busy" in caplog.text)
    assert codes == [0, 1, 1, 1]
    assert busy == [False, False, True, False]
    assert opener.calls == [(watch_cli.DEFAULT_PORT, False)] * 4
    for port in fresh:
        assert port.writes == [b"TONE,0\n"]
        assert port.closed


def test_17_first_line_wait() -> None:
    quiet = FakePort([], answers=["A,4,0"])
    started = time.monotonic()
    assert watch_cli.send_command(quiet, "TONE,0", first_line_s=0.1) == 0
    write_at = next(at for kind, at, _ in quiet.events if kind == "write")
    assert write_at - started >= 0.1

    talking = FakePort(["T,0,11,250000"], answers=["A,4,0"])
    started = time.monotonic()
    assert watch_cli.send_command(talking, "TONE,0") == 0
    kinds = [(kind, raw) for kind, _, raw in talking.events]
    assert kinds[:2] == [("read", b"T,0,11,250000\n"), ("write", b"TONE,0\n")]
    write_at = next(at for kind, at, _ in talking.events if kind == "write")
    assert write_at - started < 1.0


class FakeSerial:
    """Stands in for serial.Serial and notes each setting and the open."""

    notes: list[tuple[str, Any]] = []

    def __init__(self: FakeSerial) -> None:
        object.__setattr__(self, "state", {"dtr": None, "rts": None, "open": False})

    def __setattr__(self: FakeSerial, name: str, value: Any) -> None:
        if name in ("dtr", "rts"):
            FakeSerial.notes.append((name, value))
        self.state[name] = value

    def open(self: FakeSerial) -> None:
        FakeSerial.notes.append(("open", (self.state["dtr"], self.state["rts"])))
        self.state["open"] = True


def test_18_open_port(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("serial")
    fake.Serial = FakeSerial  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "serial", fake)

    FakeSerial.notes = []
    ser = watch_cli.open_port("/dev/fake", reset=False)
    notes = FakeSerial.notes
    opened = notes.index(("open", (True, False)))
    assert notes[opened + 1 :] == [("dtr", False)]
    assert ("rts", True) not in notes
    assert ser.state["port"] == "/dev/fake"

    FakeSerial.notes = []
    watch_cli.open_port("/dev/fake", reset=True)
    notes = FakeSerial.notes
    opened = notes.index(("open", (False, False)))
    after = notes[opened + 1 :]
    assert [n for n in after if n[0] == "rts"] == [("rts", True), ("rts", False)]
    assert ("dtr", True) not in after


def test_19_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lines = boot_lines("A,1,0")
    port = FakePort(lines, interrupt=True)
    opener = PortOpener([port])
    monkeypatch.setattr(watch_cli, "open_port", opener)
    out = tmp_path / "rec.txt.gz"
    before_us = time.time_ns() // 1000
    assert watch_cli.record("/dev/fake", out, None) == 0
    after_us = time.time_ns() // 1000
    assert opener.calls == [("/dev/fake", True)]
    assert port.closed

    entries = saved_entries(out)
    texts = [text for _, text in entries]
    assert len(texts) == len(lines) + 1
    assert texts[:3] == lines[:3]
    assert texts[4:] == lines[3:]
    found = re.fullmatch(r"> (CLOCK,(\d+),(-?\d+))", texts[3])
    assert found is not None
    assert before_us <= int(found.group(2)) <= after_us
    offset = datetime.now().astimezone().utcoffset() or timedelta(0)
    assert int(found.group(3)) == offset // timedelta(minutes=1)
    times = [stamp for stamp, _ in entries]
    assert all(re.fullmatch(r"[0-9]+\.[0-9]{3}", stamp) for stamp in times)
    seconds = [float(stamp) for stamp in times]
    assert seconds == sorted(seconds)
    assert port.writes == [(found.group(1) + "\n").encode()]


def test_20_record_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lines = boot_lines("A,1,3")
    port = FakePort(lines, interrupt=True)
    opener = PortOpener([port])
    monkeypatch.setattr(watch_cli, "open_port", opener)
    out = tmp_path / "rec.txt.gz"
    assert watch_cli.record("/dev/fake", out, None) == 1
    texts = [text for _, text in saved_entries(out)]
    assert texts[:3] + texts[4:] == lines
    assert texts[3].startswith("> CLOCK,")

    kept = tmp_path / "kept.txt.gz"
    kept.write_bytes(b"saved before")
    unused = PortOpener([FakePort(lines, interrupt=True)])
    monkeypatch.setattr(watch_cli, "open_port", unused)
    assert watch_cli.record("/dev/fake", kept, None) == 1
    assert unused.calls == []
    assert kept.read_bytes() == b"saved before"


def test_20b_record_sets_the_clock_after_each_restart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = boot_lines("A,1,0")
    second = [line.replace("B,305419896,", "B,2271560481,") for line in boot_lines("A,1,5")]
    second.insert(second.index("A,1,5") + 1, "A,1,0")
    # A repeated B line of a boot whose clock is set gets no command.
    again = next(line for line in second if line.startswith("B,"))
    port = FakePort([*first, *second, again], interrupt=True)
    monkeypatch.setattr(watch_cli, "open_port", PortOpener([port]))
    assert watch_cli.record("/dev/fake", tmp_path / "rec.txt.gz", None) == 0
    assert len(port.writes) == 3
    assert all(write.startswith(b"CLOCK,") for write in port.writes)

    busy = [line.replace("B,305419896,", "B,2271560481,") for line in boot_lines("A,1,5")]
    index = busy.index("A,1,5")
    busy[index + 1:index + 1] = ["A,1,5", "A,1,5"]
    port = FakePort([*first, *busy], interrupt=True)
    monkeypatch.setattr(watch_cli, "open_port", PortOpener([port]))
    assert watch_cli.record("/dev/fake", tmp_path / "busy.txt.gz", None) == 1
    assert len(port.writes) == 1 + watch_cli.CLOCK_TRIES


class SignalPort(FakePort):
    """A port that sends a signal to this process when its lines run out."""

    def __init__(self: SignalPort, lines: list[str], number: int) -> None:
        super().__init__(lines)
        self.number = number

    def readline(self: SignalPort) -> bytes:
        if not self.waiting:
            os.kill(os.getpid(), self.number)
        return super().readline()


class LostPort(FakePort):
    """A port whose lines end in an OSError, as when the cable comes out."""

    def readline(self: LostPort) -> bytes:
        if not self.waiting:
            raise OSError(6, "Device not configured")
        return super().readline()


class GoneOpener(PortOpener):
    """Hands out a first port, then fails for some seconds as a port that is gone, then hands out the rest."""

    def __init__(self: GoneOpener, ports: list[FakePort], gone_s: float) -> None:
        super().__init__(ports)
        self.gone_s = gone_s
        self.gone_at: float | None = None

    def __call__(self: GoneOpener, port: str, reset: bool) -> FakePort:
        if not reset:
            if self.gone_at is None:
                self.gone_at = time.monotonic()
            if time.monotonic() < self.gone_at + self.gone_s:
                self.calls.append((port, reset))
                raise OSError(2, "No such file or directory")
        return super().__call__(port, reset)


@pytest.mark.parametrize("number", [signal.SIGTERM, signal.SIGHUP])
def test_21a_record_stops_whole_at_sigterm_and_sighup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                      number: int) -> None:
    before = signal.getsignal(number)
    lines = boot_lines("A,1,0")
    port = SignalPort(lines, number)
    monkeypatch.setattr(watch_cli, "open_port", PortOpener([port]))
    out = tmp_path / "rec.txt.gz"
    assert watch_cli.record("/dev/fake", out, None) == 0
    assert port.closed
    # The file reads to its end, so the gzip stream was closed whole.
    texts = [text for _, text in saved_entries(out)]
    assert texts[:3] + texts[4:] == lines
    assert signal.getsignal(number) == before


def test_21b_held_stops_wait_for_the_block() -> None:
    stops = watch_cli.StopSignals()
    before = {number: signal.getsignal(number) for number in watch_cli.STOP_SIGNALS}
    # A second thread can take the signal from the kernel, as threads in the
    # test run do. The stop must still wait for the block.
    done = threading.Event()
    other = threading.Thread(target=done.wait)
    other.start()
    stops.install()
    try:
        reached = False
        with pytest.raises(watch_cli.Stopped):
            with stops.held():
                os.kill(os.getpid(), signal.SIGTERM)
                time.sleep(0.05)
                reached = True
        assert reached
        with pytest.raises(KeyboardInterrupt):
            with stops.held():
                with stops.held():
                    os.kill(os.getpid(), signal.SIGINT)
                    time.sleep(0.05)
                assert stops.pending is not None
        with pytest.raises(watch_cli.Stopped):
            os.kill(os.getpid(), signal.SIGHUP)
            time.sleep(0.05)
    finally:
        stops.restore()
        done.set()
        other.join()
    assert {number: signal.getsignal(number) for number in watch_cli.STOP_SIGNALS} == before


def test_21c_record_waits_for_a_port_that_is_gone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                  caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(watch_cli, "PORT_WAIT_S", 0.1)
    first = LostPort(boot_lines("A,1,0"))
    later = FakePort(["T,11,11,346200"], interrupt=True)
    opener = GoneOpener([first, later], gone_s=0.5)
    monkeypatch.setattr(watch_cli, "open_port", opener)
    out = tmp_path / "rec.txt.gz"
    started = time.monotonic()
    with caplog.at_level(logging.INFO):
        assert watch_cli.record("/dev/fake", out, None) == 0
    assert time.monotonic() - started >= 0.5
    assert "has been gone" in caplog.text and "is back" in caplog.text
    assert first.closed and later.closed
    texts = [text for _, text in saved_entries(out)]
    assert texts[-1] == "T,11,11,346200"

    opener = GoneOpener([LostPort(boot_lines("A,1,0"))], gone_s=1e9)
    monkeypatch.setattr(watch_cli, "open_port", opener)
    caplog.clear()
    with caplog.at_level(logging.INFO):
        assert watch_cli.record("/dev/fake", tmp_path / "gone.txt.gz", 0.01) == 0
    assert "while the port /dev/fake was gone" in caplog.text
    assert len(saved_entries(tmp_path / "gone.txt.gz")) == len(boot_lines("A,1,0")) + 1


def test_21_python_rules() -> None:
    for path in TYPED_FILES:
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = node.args
                every = [*args.posonlyargs, *args.args, *args.kwonlyargs]
                every += [a for a in (args.vararg, args.kwarg) if a is not None]
                for arg in every:
                    assert arg.annotation is not None, f"{path.name} {node.name} argument {arg.arg}"
                assert node.returns is not None, f"{path.name} {node.name}"
    for path in (TOOL, COMPARE):
        source = path.read_text(encoding="utf-8")
        assert "print(" not in source, path.name
        assert "os.path" not in source, path.name
        assert "except Exception" not in source, path.name
    for line in TOOL.read_text(encoding="utf-8").splitlines():
        assert not line.startswith(("import serial", "from serial")), line
