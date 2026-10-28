"""Read a saved recording into lines, and read the record patterns.

tools/compare_session.py and tools/export_edf.py share these readers. A saved
recording is the gzip text that tools/watch_cli.py writes, as the Saved
recordings section of core/recording_format.md describes. The record line
patterns come from the table in the same file.
"""
from __future__ import annotations

import gzip
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

FORMAT_DOC = REPO / "core" / "recording_format.md"
RECORD_LETTERS = "BSTRWFDA"

READ_CHUNK = 1 << 16


def record_patterns(doc: Path = FORMAT_DOC) -> dict[str, re.Pattern[str]]:
    """Read the pattern of each record line from the table in core/recording_format.md."""
    patterns: dict[str, re.Pattern[str]] = {}
    for row in doc.read_text().splitlines():
        match = re.match(r"^\| ([A-Z]) \|.*\| `(\^.*\$)` \|$", row)
        if match:
            patterns[match.group(1)] = re.compile(match.group(2))
    if sorted(patterns) != sorted(RECORD_LETTERS):
        raise ValueError(f"{doc} gives patterns for {''.join(sorted(patterns))}, not for {RECORD_LETTERS}")
    return patterns


def read_gzip_text(path: Path) -> tuple[list[str], bool]:
    """Read the lines of a gzip text file, and tell whether the file was cut short.

    A recording that stopped without closing its file ends in the middle of
    the gzip stream. The lines read before the cut are kept, and a last line
    with no newline is dropped, because it may be part of a line.
    """
    data = bytearray()
    cut_short = False
    with gzip.open(path, "rb") as source:
        while True:
            try:
                # read1() gives what one step decompresses. read() collects
                # several steps and loses them all when the stream ends early.
                chunk = source.read1(READ_CHUNK)
            except EOFError:
                cut_short = True
                break
            if not chunk:
                break
            data += chunk
    lines = data.decode(errors="replace").splitlines()
    if cut_short and lines and not data.endswith(b"\n"):
        lines.pop()
    return lines, cut_short


def read_recording(path: Path) -> tuple[list[str], bool]:
    """Read a recording as gzip or plain text and drop a leading laptop time and tab.

    It also tells whether a gzip file was cut short.
    """
    cut_short = False
    if path.name.endswith(".gz"):
        raw_lines, cut_short = read_gzip_text(path)
    else:
        raw_lines = path.read_text(errors="replace").splitlines()
    lines: list[str] = []
    for raw in raw_lines:
        stamp, tab, text = raw.partition("\t")
        try:
            float(stamp)
        except ValueError:
            lines.append(raw)
            continue
        lines.append(text if tab else raw)
    return lines, cut_short
