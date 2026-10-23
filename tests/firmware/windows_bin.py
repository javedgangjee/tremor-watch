"""Turn the saved windows into little-endian 32-bit floats for the chip.

firmware/detector_check/ runs this script at build time and embeds its output.
It reads tests/detector/windows.csv, checks the header and the count of rows,
and casts each value from Python's float() to a 32-bit float, in file order.
It uses only the standard library, because it runs with the ESP-IDF Python.

    python tests/firmware/windows_bin.py --csv tests/detector/windows.csv --out windows.bin
"""
from __future__ import annotations

import argparse
import csv
import logging
import struct
from pathlib import Path

LOG = logging.getLogger("windows_bin")

HEADER = ["gyroscope_x", "gyroscope_y", "gyroscope_z"]
WINDOWS = 322
WINDOW_LEN = 400
ROWS = WINDOWS * WINDOW_LEN


def windows_bytes(path: Path) -> bytes:
    """Give the saved windows as little-endian 32-bit floats in file order."""
    with path.open(newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != HEADER:
            raise ValueError(f"{path} has the header {header}, not {HEADER}")
        values: list[float] = []
        rows = 0
        for row in reader:
            if len(row) != len(HEADER):
                raise ValueError(f"{path} row {rows + 1} has {len(row)} values")
            values.extend(float(text) for text in row)
            rows += 1
    if rows != ROWS:
        raise ValueError(f"{path} has {rows} rows, not {ROWS}")
    return struct.pack(f"<{len(values)}f", *values)


def main(argv: list[str] | None = None) -> int:
    """Write the binary file and give the exit code."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    data = windows_bytes(args.csv)
    args.out.write_bytes(data)
    LOG.info("wrote %d bytes to %s", len(data), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
