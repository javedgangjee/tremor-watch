"""Set up the watch over USB and save its recording.

The tool sends the commands of core/recording_format.md to the watch. It sets
the dose clock, sets or clears the dose schedule, starts a new session, and
turns the tone on or off. It also resets the watch, saves every line it writes
to a gzip text file, and sets the clock as soon as the watch has booted.

It needs pyserial, so it runs with the ESP-IDF Python.

    ~/.espressif/tools/python/v6.1/venv/bin/python tools/watch_cli.py clock
    ~/.espressif/tools/python/v6.1/venv/bin/python tools/watch_cli.py schedule Levodopa 08:00 20:00
    ~/.espressif/tools/python/v6.1/venv/bin/python tools/watch_cli.py schedule --off
    ~/.espressif/tools/python/v6.1/venv/bin/python tools/watch_cli.py session
    ~/.espressif/tools/python/v6.1/venv/bin/python tools/watch_cli.py tone off
    ~/.espressif/tools/python/v6.1/venv/bin/python tools/watch_cli.py record --out FILE [--minutes M]

A command exits with code 0 only when the watch answers it with result 0. The
tool refuses a name or a time that the watch would refuse, before it opens the
port, and exits with code 2. A recording stops after --minutes or at Ctrl-C.
"""
from __future__ import annotations

import argparse
import gzip
import logging
import re
import signal
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TextIO

LOG = logging.getLogger("watch_cli")

DEFAULT_PORT = "/dev/cu.usbmodem101"
FIRST_LINE_S = 2.0
ANSWER_S = 5.0
PORT_WAIT_S = 10.0
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
COMMAND_NUMBERS = {"CLOCK": 1, "SCHEDULE": 2, "SESSION": 3, "TONE": 4}
NAME_PATTERN = re.compile(r"[A-Za-z0-9./+-]{1,20}")
TIME_PATTERN = re.compile(r"([01][0-9]|2[0-3]):([0-5][0-9])")
ANSWER_PATTERN = re.compile(r"A,([0-9]+),([0-9]+)")
MAX_TIMES = 6
RESULTS = {
    0: "The watch applied the command.",
    1: "The watch does not know the command.",
    2: "The watch found that the line breaks the format.",
    3: "The watch found a value outside its range.",
    4: "The watch applied the setting but could not store it, so a restart loses it.",
    5: "The watch was busy and dropped the command. The command may be sent again.",
}


def clock_command(now_utc: datetime, offset: timedelta) -> str:
    """Give the CLOCK command for a UTC time and a local offset."""
    utc_us = (now_utc - EPOCH) // timedelta(microseconds=1)
    offset_min = offset // timedelta(minutes=1)
    return f"CLOCK,{utc_us},{offset_min}"


def schedule_command(name: str | None, times: list[str]) -> str:
    """Give the SCHEDULE command for a name and times as HH:MM.

    It raises ValueError for a name or a time that the watch would refuse.
    """
    if name is None:
        if times:
            raise ValueError("a dose time needs a medicine name")
        return "SCHEDULE"
    if NAME_PATTERN.fullmatch(name) is None:
        raise ValueError(
            f"the name {name!r} must have 1 to 20 characters, each a letter, a digit, or one of - . / +"
        )
    if len(times) > MAX_TIMES:
        raise ValueError(f"the schedule holds at most {MAX_TIMES} times, and {len(times)} were given")
    minutes: list[int] = []
    for text in times:
        found = TIME_PATTERN.fullmatch(text)
        if found is None:
            raise ValueError(f"the time {text!r} must be HH:MM from 00:00 to 23:59")
        minute = int(found.group(1)) * 60 + int(found.group(2))
        if minute in minutes:
            raise ValueError(f"the time {text} is given twice")
        minutes.append(minute)
    return ",".join(["SCHEDULE", name, *(str(m) for m in minutes)])


def tone_command(on: bool) -> str:
    """Give the TONE command that turns the tone on or off."""
    return f"TONE,{1 if on else 0}"


def session_command() -> str:
    """Give the SESSION command."""
    return "SESSION"


def open_port(port: str, reset: bool) -> Any:
    """Open the port with DTR and RTS low. With reset, pulse RTS to reset the
    chip as esptool's hard reset does.

    This is a copy of open_port() in tests/firmware/record_run.py, because a
    tool does not import from tests/.
    """
    import serial

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = 115200
    ser.timeout = 0.5
    # The chip resets while RTS is high and DTR is low. pyserial sets DTR
    # before RTS when it opens the port, so a port opened with both low passes
    # through that state and resets the chip. Opening with DTR high and RTS low
    # and then dropping DTR never passes through it.
    ser.dtr = not reset
    ser.rts = False
    ser.open()
    ser.dtr = False
    if reset:
        ser.rts = True
        time.sleep(0.1)
        ser.rts = False
    return ser


def reopen(port: str) -> Any:
    """Open the port again with no reset, waiting up to PORT_WAIT_S seconds.

    The port can vanish for a moment while the watch resets.
    """
    end = time.monotonic() + PORT_WAIT_S
    while True:
        try:
            return open_port(port, reset=False)
        except OSError:
            if time.monotonic() > end:
                raise
            time.sleep(0.2)


def read_raw(ser: Any) -> bytes:
    """Read one line as bytes, or b"" when nothing came in the port's timeout.

    When the read stops in the middle of a line, it reads once more for the
    rest. The result then ends with a newline only when the line is whole.
    """
    raw = bytes(ser.readline())
    if raw and not raw.endswith(b"\n"):
        raw += bytes(ser.readline())
    return raw


def text_of(raw: bytes) -> str:
    """Turn the bytes of one line into text without its line end."""
    return raw.decode(errors="replace").rstrip("\r\n")


def command_number(command: str) -> int:
    """Give the number that the watch's A line uses for a command."""
    return COMMAND_NUMBERS.get(command.split(",", 1)[0], 0)


def send_command(
    ser: Any,
    command: str,
    first_line_s: float = 2.0,
    answer_s: float = 5.0,
    on_line: Callable[[str], None] | None = None,
) -> int | None:
    """Send one command and give the result of its A line, or None when no
    answer came.

    It first reads until one whole line arrives or first_line_s passes, so the
    watch's send buffer has room for the answer. It then writes the command
    once and reads until the A line with the command's number arrives or
    answer_s passes. Every line it reads goes to on_line when one is given.
    """
    end = time.monotonic() + first_line_s
    while time.monotonic() < end:
        raw = read_raw(ser)
        if not raw:
            continue
        if on_line is not None:
            on_line(text_of(raw))
        if raw.endswith(b"\n"):
            break
    ser.write((command + "\n").encode())
    number = command_number(command)
    end = time.monotonic() + answer_s
    while time.monotonic() < end:
        raw = read_raw(ser)
        if not raw:
            continue
        text = text_of(raw)
        if on_line is not None:
            on_line(text)
        found = ANSWER_PATTERN.fullmatch(text)
        if found is not None and int(found.group(1)) == number:
            return int(found.group(2))
    return None


def write_entry(out: TextIO, started: float, text: str) -> None:
    """Write one line to the open gzip file with the laptop's time."""
    out.write(f"{time.monotonic() - started:.3f}\t{text}\n")


def laptop_clock_command() -> str:
    """Give the CLOCK command for the laptop's time and local offset now."""
    now_utc = EPOCH + timedelta(microseconds=time.time_ns() // 1000)
    offset = datetime.now().astimezone().utcoffset() or timedelta(0)
    return clock_command(now_utc, offset)


def record(port: str, out: Path, minutes: float | None) -> int:
    """Reset the watch and save every line it writes to a gzip text file.

    Each line is saved as the laptop's seconds since the port opened, a tab,
    and the text. Right after the first B line the clock command follows as a
    line that starts with "> ". It stops after the given minutes, or at
    KeyboardInterrupt when no minutes are given. It gives 1 when the file
    exists or the clock command did not get result 0, and 0 otherwise.
    """
    if out.exists():
        LOG.error("%s exists already. The tool does not write over a saved recording.", out)
        return 1
    if not out.parent.is_dir():
        LOG.error("The folder %s does not exist.", out.parent)
        return 1
    ser = open_port(port, reset=True)
    started = time.monotonic()
    end = None if minutes is None else started + minutes * 60
    clock_sent = False
    clock_result: int | None = None
    lines = 0
    with gzip.open(out, "xt") as saved:

        def save(text: str) -> None:
            nonlocal lines
            write_entry(saved, started, text)
            lines += 1

        LOG.info("Saving the recording to %s. Press Ctrl-C to stop.", out)
        try:
            while end is None or time.monotonic() < end:
                try:
                    raw = read_raw(ser)
                except OSError:
                    ser.close()
                    ser = reopen(port)
                    continue
                if not raw:
                    continue
                text = text_of(raw)
                save(text)
                if clock_sent or not text.startswith("B,"):
                    continue
                clock_sent = True
                command = laptop_clock_command()
                LOG.info("The watch booted with %s. Sending %s.", text, command)
                save(f"> {command}")
                try:
                    clock_result = send_command(ser, command, first_line_s=0, on_line=save)
                except OSError:
                    ser.close()
                    ser = reopen(port)
                    continue
                if clock_result == 0:
                    LOG.info("The watch set its clock.")
                else:
                    LOG.error("The clock command got %s", answer_text(clock_result))
        except KeyboardInterrupt:
            LOG.info("The recording was stopped.")
        finally:
            ser.close()
    LOG.info("Saved %d lines to %s.", lines, out)
    if not clock_sent:
        LOG.error("No B line came, so the clock was not set.")
    return 0 if clock_result == 0 else 1


def answer_text(result: int | None) -> str:
    """Describe a command's result in words."""
    if result is None:
        return "no answer."
    return f"result {result}. {RESULTS.get(result, 'The result is unknown.')}"


def run_command(port: str, command: str) -> int:
    """Send one command to the watch with no reset and give the exit code."""
    ser = open_port(port, reset=False)
    try:
        result = send_command(ser, command, FIRST_LINE_S, ANSWER_S)
    finally:
        ser.close()
    if result is None:
        LOG.error("No answer to %s came within %.0f seconds.", command, ANSWER_S)
        return 1
    LOG.info("A,%d,%d", command_number(command), result)
    if result == 0:
        LOG.info(RESULTS[0])
        return 0
    LOG.error(RESULTS.get(result, "The result is unknown."))
    return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the parser of the command line."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--port", default=DEFAULT_PORT)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("clock", help="set the dose clock to the laptop's time")
    schedule = sub.add_parser("schedule", help="set the medicine name and dose times, or turn the schedule off")
    schedule.add_argument("name", nargs="?")
    schedule.add_argument("times", nargs="*", metavar="HH:MM")
    schedule.add_argument("--off", action="store_true", help="turn the schedule off and clear the name")
    sub.add_parser("session", help="start a new session")
    tone = sub.add_parser("tone", help="turn the tone on or off")
    tone.add_argument("state", choices=["on", "off"])
    rec = sub.add_parser("record", help="reset the watch and save its recording")
    rec.add_argument("--out", type=Path, required=True)
    rec.add_argument("--minutes", type=float, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand and give the exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # A shell that starts a job in the background can set SIGINT to be
    # ignored. Putting Python's own handler back lets Ctrl-C and kill -INT
    # stop a recording in every case.
    signal.signal(signal.SIGINT, signal.default_int_handler)

    if args.action == "record":
        return record(args.port, args.out, args.minutes)
    if args.action == "clock":
        command = laptop_clock_command()
    elif args.action == "session":
        command = session_command()
    elif args.action == "tone":
        command = tone_command(args.state == "on")
    else:
        if args.off and (args.name is not None or args.times):
            LOG.error("schedule --off takes no name and no time.")
            return 2
        if not args.off and args.name is None:
            LOG.error("schedule needs a name, or --off to turn the schedule off.")
            return 2
        try:
            command = schedule_command(args.name, args.times)
        except ValueError as error:
            LOG.error("The watch would refuse this schedule: %s.", error)
            return 2
    LOG.info("Sending %s to %s.", command, args.port)
    return run_command(args.port, command)


if __name__ == "__main__":
    raise SystemExit(main())
