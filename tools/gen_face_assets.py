"""Make the watch face's fonts, icons, and font metrics.

The fonts come from Red Hat Display Bold, the static font of tag 5.0.0 of
github.com/RedHatOfficial/RedHatFont, which is commit
6bb1048a6402b0076ea04f42951ec66263cd1437. The file
fonts/Proportional/RedHatDisplay/ttf/RedHatDisplay-Bold.ttf of that commit has
the SHA-256 hash bac4990e2845c796ad0cfc47c3121b09df9285858ba841f7eab8bcdea87b74f1,
and the tool stops when the font file has another hash.

lv_font_conv 1.5.3 converts the font through npx at 28, 40, 56, and 96 pixels,
with 4 bits a pixel, no compression, and no kerning. The tool reads each output's
line height, base line, and advance widths, and it writes core/face_metrics.h,
so the laptop can measure a text as LVGL 9.5.0 does.

The icons come from Lucide 0.469.0. The tool draws each one from its path data
with numpy as an 8-bit alpha image, so LVGL can colour it, and writes them as C
arrays in firmware/main/assets/face_icons.c.

The tool runs in the reference venv, which has numpy, and the same run gives
the same bytes. Run it from the repo root with this command.

    reference/.venv/bin/python tools/gen_face_assets.py
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import math
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import numpy as np

logger = logging.getLogger("gen_face_assets")

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ASSETS = REPO / "firmware" / "main" / "assets"
DEFAULT_FONT = DEFAULT_ASSETS / "RedHatDisplay-Bold.ttf"
DEFAULT_METRICS = REPO / "core" / "face_metrics.h"
FONT_SHA256 = "bac4990e2845c796ad0cfc47c3121b09df9285858ba841f7eab8bcdea87b74f1"
COMMAND = "reference/.venv/bin/python tools/gen_face_assets.py"
FONT_CONV = ["npx", "--yes", "lv_font_conv@1.5.3"]
# The converter runs in a scratch folder that mirrors these repo paths, so the
# options line in each font file is the same on every laptop.
FONT_IN_RUN = "firmware/main/assets/RedHatDisplay-Bold.ttf"
OUT_IN_RUN = "firmware/main/assets"

# Each size and its range of characters. The 96 pixel font holds only what
# the time needs.
FONT_RANGES: dict[int, str] = {
    28: "0x20-0x7E",
    40: "0x20-0x7E",
    56: "0x20-0x7E",
    96: "0x20,0x2D,0x30-0x3A",
}
FIRST_CHAR = 0x20
LAST_CHAR = 0x7E

# ICON_PX leaves room in the circle for "Tremor Detected" on two lines below
# the icon. BUTTON_ICON_PX is the size of the "Took it" button's check.
ICON_PX = 128
BUTTON_ICON_PX = 88
BUTTON_ICONS = ("face_icon_check",)
LUCIDE_GRID = 24.0
LUCIDE_STROKE = 1.5
# Curves and arcs turn into pieces of at most this length on Lucide's grid.
PIECE_LEN = 0.1
# The distances are found for this many pieces at a time, which bounds the memory.
PIECES_AT_ONCE = 128
BYTES_PER_LINE = 16

# An element is ("path", d), ("circle", cx, cy, r), or
# ("rect", x, y, w, h, rx).
Element = tuple[str | float, ...]

# The path data of Lucide 0.469.0, from lucide-static@0.469.0/icons/*.svg.
# clock's polyline "12 6 12 12 16 14" is written as a path with the same points.
LUCIDE_ICONS: dict[str, list[Element]] = {
    "face_icon_tremor": [  # activity
        ("path", "M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0"
                 "l-2.35 8.36A2 2 0 0 1 4.49 12H2"),
    ],
    "face_icon_no_tremor": [  # minus
        ("path", "M5 12h14"),
    ],
    "face_icon_arm_moving": [  # vibrate
        ("path", "m2 8 2 2-2 2 2 2-2 2"),
        ("path", "m22 8-2 2 2 2-2 2 2 2"),
        ("rect", 8.0, 5.0, 8.0, 14.0, 1.0),
    ],
    "face_icon_waiting": [  # clock
        ("circle", 12.0, 12.0, 10.0),
        ("path", "M12 6 12 12 16 14"),
    ],
    "face_icon_dose_due": [  # pill
        ("path", "m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z"),
        ("path", "m8.5 8.5 7 7"),
    ],
    "face_icon_check": [  # check
        ("path", "M20 6 9 17l-5-5"),
    ],
    "face_icon_logged_ring": [  # circle-check-big, its ring
        ("path", "M21.801 10A10 10 0 1 1 17 3.335"),
    ],
    "face_icon_logged_tick": [  # circle-check-big, its tick
        ("path", "m9 11 3 3L22 4"),
    ],
}

NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
COMMANDS = "MmLlHhVvCcSsAaZz"
ARGS_PER_COMMAND = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "a": 7, "z": 0}

Points = list[tuple[float, float]]


@dataclass(frozen=True)
class FontMetrics:
    """One font's line height, base line, and the advance width of each character from space to ~."""

    line_height: int
    base_line: int
    widths: list[int]


def fail(message: str) -> NoReturn:
    """Log the reason and stop the run with exit code 1."""
    logger.error(message)
    sys.exit(1)


def sha256_of(path: Path) -> str:
    """Return the SHA-256 hash of the file's bytes as 64 hex characters."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------- path data


def parse_path(d: str) -> list[tuple[str, list[float]]]:
    """Read SVG path data into commands with their numbers.

    A command that repeats without its letter gives one entry per set of
    numbers, and numbers after M or m count as L or l. The two flags of an arc
    are read as single digits, because path data may write them with no space.
    """
    out: list[tuple[str, list[float]]] = []
    i = 0
    command = ""
    while i < len(d):
        ch = d[i]
        if ch in COMMANDS:
            command = ch
            i += 1
            if command in "Zz":
                out.append((command, []))
            continue
        if ch in " ,\t\n":
            i += 1
            continue
        if not command or command in "Zz":
            raise ValueError(f"path data has numbers with no command at {i}: {d!r}")
        need = ARGS_PER_COMMAND[command.lower()]
        numbers: list[float] = []
        while len(numbers) < need:
            while i < len(d) and d[i] in " ,\t\n":
                i += 1
            if command in "Aa" and len(numbers) in (3, 4):
                if i >= len(d) or d[i] not in "01":
                    raise ValueError(f"an arc flag is not 0 or 1 at {i}: {d!r}")
                numbers.append(float(d[i]))
                i += 1
                continue
            match = NUMBER.match(d, i)
            if match is None:
                raise ValueError(f"path data lacks a number at {i}: {d!r}")
            numbers.append(float(match.group()))
            i = match.end()
        out.append((command, numbers))
        if command == "M":
            command = "L"
        elif command == "m":
            command = "l"
    return out


def pieces_for(length: float) -> int:
    """Return how many straight pieces a curve of about this length needs."""
    return max(8, math.ceil(length / PIECE_LEN))


def cubic_points(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float],
                 p3: tuple[float, float]) -> Points:
    """Return points along a cubic curve, leaving out its start."""
    rough = math.dist(p0, p1) + math.dist(p1, p2) + math.dist(p2, p3)
    t = np.linspace(0.0, 1.0, pieces_for(rough) + 1)[1:]
    mt = 1.0 - t
    x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
    y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
    return list(zip(x.tolist(), y.tolist(), strict=True))


def arc_points(p0: tuple[float, float], rx: float, ry: float, angle_deg: float, large: bool, sweep: bool,
               p1: tuple[float, float]) -> Points:
    """Return points along an SVG arc, leaving out its start.

    This follows the endpoint to centre conversion in appendix B.2.4 of the
    SVG 1.1 specification, with radii that are too small scaled up.
    """
    if p0 == p1:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx == 0.0 or ry == 0.0:
        return [p1]
    phi = math.radians(angle_deg)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2.0, (p0[1] - p1[1]) / 2.0
    x1p = cos_p * dx + sin_p * dy
    y1p = -sin_p * dx + cos_p * dy
    scale = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if scale > 1.0:
        rx *= math.sqrt(scale)
        ry *= math.sqrt(scale)
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    root = math.sqrt(max(0.0, num / den))
    if large == sweep:
        root = -root
    cxp = root * rx * y1p / ry
    cyp = -root * ry * x1p / rx
    cx = cos_p * cxp - sin_p * cyp + (p0[0] + p1[0]) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (p0[1] + p1[1]) / 2.0

    def angle(ux: float, uy: float, vx: float, vy: float) -> float:
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

    start = angle(1.0, 0.0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    delta = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi
    t = start + delta * np.linspace(0.0, 1.0, pieces_for(abs(delta) * max(rx, ry)) + 1)[1:]
    ex = rx * np.cos(t)
    ey = ry * np.sin(t)
    x = cos_p * ex - sin_p * ey + cx
    y = sin_p * ex + cos_p * ey + cy
    points = list(zip(x.tolist(), y.tolist(), strict=True))
    points[-1] = p1
    return points


def path_points(d: str) -> list[Points]:
    """Turn SVG path data into lines of points on Lucide's grid, one line for each subpath."""
    lines: list[Points] = []
    current: Points = []
    x = y = 0.0
    start = (0.0, 0.0)
    last_control: tuple[float, float] | None = None
    for command, n in parse_path(d):
        rel = command.islower()
        kind = command.lower()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        control: tuple[float, float] | None = None
        if kind == "m":
            if len(current) > 1:
                lines.append(current)
            x, y = ox + n[0], oy + n[1]
            start = (x, y)
            current = [(x, y)]
        elif kind == "l":
            x, y = ox + n[0], oy + n[1]
            current.append((x, y))
        elif kind == "h":
            x = (x if rel else 0.0) + n[0]
            current.append((x, y))
        elif kind == "v":
            y = (y if rel else 0.0) + n[0]
            current.append((x, y))
        elif kind == "c":
            p1 = (ox + n[0], oy + n[1])
            p2 = (ox + n[2], oy + n[3])
            p3 = (ox + n[4], oy + n[5])
            current.extend(cubic_points((x, y), p1, p2, p3))
            control = p2
            x, y = p3
        elif kind == "s":
            p1 = (2 * x - last_control[0], 2 * y - last_control[1]) if last_control else (x, y)
            p2 = (ox + n[0], oy + n[1])
            p3 = (ox + n[2], oy + n[3])
            current.extend(cubic_points((x, y), p1, p2, p3))
            control = p2
            x, y = p3
        elif kind == "a":
            end = (ox + n[5], oy + n[6])
            current.extend(arc_points((x, y), n[0], n[1], n[2], n[3] != 0.0, n[4] != 0.0, end))
            x, y = end
        elif kind == "z":
            current.append(start)
            x, y = start
            lines.append(current)
            current = [start]
        last_control = control
    if len(current) > 1:
        lines.append(current)
    return lines


def circle_points(cx: float, cy: float, r: float) -> Points:
    """Return a closed line of points around a circle."""
    t = np.linspace(0.0, 2 * math.pi, pieces_for(2 * math.pi * r) + 1)
    points = list(zip((cx + r * np.cos(t)).tolist(), (cy + r * np.sin(t)).tolist(), strict=True))
    points[-1] = points[0]
    return points


def rect_points(x: float, y: float, w: float, h: float, rx: float) -> Points:
    """Return a closed line of points around a rectangle with round corners of radius rx."""
    r = min(rx, w / 2.0, h / 2.0)
    if r <= 0.0:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
    d = (f"M{x + r} {y}H{x + w - r}A{r} {r} 0 0 1 {x + w} {y + r}V{y + h - r}"
         f"A{r} {r} 0 0 1 {x + w - r} {y + h}H{x + r}A{r} {r} 0 0 1 {x} {y + h - r}"
         f"V{y + r}A{r} {r} 0 0 1 {x + r} {y}Z")
    return path_points(d)[0]


def element_lines(element: Element) -> list[Points]:
    """Return the lines of points of one icon element on Lucide's grid."""
    kind = element[0]
    if kind == "path":
        return path_points(str(element[1]))
    if kind == "circle":
        cx, cy, r = (float(v) for v in element[1:4])
        return [circle_points(cx, cy, r)]
    if kind == "rect":
        x, y, w, h, rx = (float(v) for v in element[1:6])
        return [rect_points(x, y, w, h, rx)]
    raise ValueError(f"unknown icon element {kind}")


def draw_icon(elements: Sequence[Element], size_px: int, stroke: float) -> np.ndarray:
    """Draw an icon as an 8-bit alpha image of size_px by size_px.

    Each pixel takes the coverage clamp(stroke / 2 + 0.5 - d, 0, 1), where d is
    the distance from the pixel's centre to the nearest straight piece, so caps
    and joins come out round.
    """
    scale = size_px / LUCIDE_GRID
    starts: list[tuple[float, float]] = []
    ends: list[tuple[float, float]] = []
    for element in elements:
        for line in element_lines(element):
            for a, b in zip(line[:-1], line[1:], strict=True):
                starts.append((a[0] * scale, a[1] * scale))
                ends.append((b[0] * scale, b[1] * scale))
    centres = np.arange(size_px, dtype=np.float64) + 0.5
    px, py = np.meshgrid(centres, centres)
    p = np.stack([px.ravel(), py.ravel()], axis=1)[:, None, :]
    d_sq = np.full(size_px * size_px, np.inf)
    for first in range(0, len(starts), PIECES_AT_ONCE):
        a = np.array(starts[first:first + PIECES_AT_ONCE], dtype=np.float64)[None, :, :]
        ab = np.array(ends[first:first + PIECES_AT_ONCE], dtype=np.float64)[None, :, :] - a
        ap = p - a
        length_sq = np.sum(ab * ab, axis=2)
        safe = np.where(length_sq > 0.0, length_sq, 1.0)
        t = np.clip(np.where(length_sq > 0.0, np.sum(ap * ab, axis=2) / safe, 0.0), 0.0, 1.0)
        nearest = ap - t[:, :, None] * ab
        d_sq = np.minimum(d_sq, np.min(np.sum(nearest * nearest, axis=2), axis=1))
    d = np.sqrt(d_sq)
    coverage = np.clip(stroke / 2.0 + 0.5 - d, 0.0, 1.0)
    return np.rint(coverage * 255.0).astype(np.uint8).reshape(size_px, size_px)


def write_image_c(name: str, pixels: np.ndarray) -> str:
    """Return the C text of one icon as an LVGL 9 image with the A8 colour format."""
    height, width = pixels.shape
    data = pixels.astype(np.uint8).ravel().tolist()
    rows = []
    for i in range(0, len(data), BYTES_PER_LINE):
        rows.append("    " + ", ".join(f"0x{v:02x}" for v in data[i:i + BYTES_PER_LINE]) + ",")
    return (
        f"static const uint8_t {name}_map[] = {{\n"
        + "\n".join(rows)
        + "\n};\n\n"
        f"const lv_image_dsc_t {name} = {{\n"
        "    .header = {\n"
        "        .magic = LV_IMAGE_HEADER_MAGIC,\n"
        "        .cf = LV_COLOR_FORMAT_A8,\n"
        "        .flags = 0,\n"
        f"        .w = {width},\n"
        f"        .h = {height},\n"
        f"        .stride = {width},\n"
        "    },\n"
        f"    .data_size = {len(data)},\n"
        f"    .data = {name}_map,\n"
        "};\n"
    )


# ---------------------------------------------------------------- fonts


def c_array(text: str, name: str) -> list[int]:
    """Return the whole numbers of the C array with this name, or an empty list."""
    match = re.search(r"\b" + re.escape(name) + r"\[\]\s*=\s*\{(.*?)\};", text, re.S)
    if match is None:
        return []
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.S)
    return [int(v, 0) for v in re.findall(r"0x[0-9a-fA-F]+|\d+", body)]


def field(block: str, name: str) -> str:
    """Return the text of one designated field in a C initialiser."""
    match = re.search(r"\." + name + r"\s*=\s*([^,}\n]+)", block)
    if match is None:
        raise ValueError(f"the font output lacks the field {name}")
    return match.group(1).strip()


def parse_font_output(text: str) -> FontMetrics:
    """Read one lv_font_conv output and return its line height, base line, and widths.

    Each width is (adv_w + 8) >> 4, which is how LVGL 9.5.0 rounds it, and a
    character that the font lacks has width 0.
    """
    line_height = int(field(text, "line_height"))
    base_line = int(field(text, "base_line"))
    dsc = re.search(r"glyph_dsc\[\]\s*=\s*\{(.*?)\n\};", text, re.S)
    if dsc is None:
        raise ValueError("the font output lacks glyph_dsc")
    advances = [int(v) for v in re.findall(r"\.adv_w\s*=\s*(\d+)", dsc.group(1))]
    cmaps = re.search(r"cmaps\[\]\s*=\s*\{(.*?)\n\};", text, re.S)
    if cmaps is None:
        raise ValueError("the font output lacks cmaps")
    glyph_of: dict[int, int] = {}
    for block in re.findall(r"\{([^{}]*range_start[^{}]*)\}", cmaps.group(1)):
        start = int(field(block, "range_start"))
        length = int(field(block, "range_length"))
        first_id = int(field(block, "glyph_id_start"))
        kind = field(block, "type")
        unicode_list = field(block, "unicode_list")
        ofs_list = field(block, "glyph_id_ofs_list")
        list_length = int(field(block, "list_length"))
        ofs = c_array(text, ofs_list) if ofs_list != "NULL" else []
        if kind.endswith("FORMAT0_TINY"):
            for i in range(length):
                glyph_of[start + i] = first_id + i
        elif kind.endswith("FORMAT0_FULL"):
            for i in range(length):
                glyph_of[start + i] = first_id + ofs[i]
        elif kind.endswith("SPARSE_TINY") or kind.endswith("SPARSE_FULL"):
            offsets = c_array(text, unicode_list)[:list_length]
            for i, off in enumerate(offsets):
                glyph_of[start + off] = first_id + (ofs[i] if kind.endswith("FULL") else i)
        else:
            raise ValueError(f"unknown cmap type {kind}")
    widths = []
    for code in range(FIRST_CHAR, LAST_CHAR + 1):
        gid = glyph_of.get(code)
        widths.append((advances[gid] + 8) >> 4 if gid is not None and gid < len(advances) else 0)
    return FontMetrics(line_height=line_height, base_line=base_line, widths=widths)


def generated_comment(what: str) -> str:
    """Return the comment that starts every generated file."""
    return f"/*\n * {what}\n * tools/gen_face_assets.py made this file. Do not edit it.\n * The command is `{COMMAND}`.\n */\n"


def run_font_conv(work: Path, size: int) -> str:
    """Run lv_font_conv for one size in the scratch folder and return its output text."""
    out_name = f"face_font_{size}.c"
    command = FONT_CONV + [
        "--size", str(size), "--bpp", "4", "--no-compress", "--format", "lvgl", "--no-kerning", "--lv-include", "lvgl.h",
        "--font", FONT_IN_RUN, "-r", FONT_RANGES[size], "-o", f"{OUT_IN_RUN}/{out_name}",
    ]
    logger.info("running %s", " ".join(command))
    subprocess.run(command, cwd=work, check=True, stdout=subprocess.DEVNULL)
    return (work / OUT_IN_RUN / out_name).read_text(encoding="utf-8")


def metrics_text(metrics: dict[int, FontMetrics]) -> str:
    """Return the text of core/face_metrics.h."""
    lines = [
        generated_comment("face_metrics.h holds each face font's line height, base line, and the advance width "
                          "of each character from space to ~ in whole pixels as LVGL 9.5.0 rounds it."),
        "#ifndef FACE_METRICS_H",
        "#define FACE_METRICS_H",
        "",
        "#include <stdint.h>",
        "",
        f"#define FACE_FIRST_CHAR 0x{FIRST_CHAR:02X}",
        f"#define FACE_LAST_CHAR 0x{LAST_CHAR:02X}",
        "",
    ]
    for size, m in metrics.items():
        lines.append(f"#define FACE_LINE_{size} {m.line_height}")
        lines.append(f"#define FACE_BASE_{size} {m.base_line}")
    lines.append("")
    for size, m in metrics.items():
        lines.append(f"/* The advance widths at {size} pixels, where 0 marks a character the font lacks. */")
        lines.append(f"static const uint8_t face_adv_{size}[{LAST_CHAR - FIRST_CHAR + 1}] = {{")
        for i in range(0, len(m.widths), BYTES_PER_LINE):
            lines.append("    " + ", ".join(str(w) for w in m.widths[i:i + BYTES_PER_LINE]) + ",")
        lines.append("};")
        lines.append("")
    lines.append("#endif /* FACE_METRICS_H */")
    return "\n".join(lines) + "\n"


def icons_texts() -> tuple[str, str]:
    """Return the texts of face_icons.c and face_icons.h."""
    body = [
        generated_comment(f"face_icons.c holds the face's Lucide 0.469.0 icons as {ICON_PX} by {ICON_PX} "
                          f"images, and the check as {BUTTON_ICON_PX} by {BUTTON_ICON_PX}, with the A8 colour format."),
        '#include "face_icons.h"',
        "",
    ]
    header = [
        generated_comment("face_icons.h names the face's icons."),
        "#ifndef FACE_ICONS_H",
        "#define FACE_ICONS_H",
        "",
        '#include "lvgl.h"',
        "",
    ]
    for name, elements in LUCIDE_ICONS.items():
        px = BUTTON_ICON_PX if name in BUTTON_ICONS else ICON_PX
        body.append(write_image_c(name, draw_icon(elements, px, px * LUCIDE_STROKE / LUCIDE_GRID)))
        header.append(f"extern const lv_image_dsc_t {name};")
    header += ["", "#endif /* FACE_ICONS_H */"]
    return "\n".join(body), "\n".join(header) + "\n"


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT, help="the Red Hat Display Bold font file")
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSETS, help="the folder for the fonts and icons")
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS, help="the metrics header to write")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Check the font, convert it, draw the icons, and write every file."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    digest = sha256_of(args.font)
    if digest != FONT_SHA256:
        fail(f"the font file {args.font} has SHA-256 {digest}, not {FONT_SHA256}")

    fonts: dict[int, str] = {}
    metrics: dict[int, FontMetrics] = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / OUT_IN_RUN).mkdir(parents=True)
        shutil.copyfile(args.font, work / FONT_IN_RUN)
        for size in FONT_RANGES:
            text = run_font_conv(work, size)
            metrics[size] = parse_font_output(text)
            fonts[size] = generated_comment(f"face_font_{size}.c is Red Hat Display Bold at {size} pixels.") + text
    icons_c, icons_h = icons_texts()

    args.assets.mkdir(parents=True, exist_ok=True)
    for size, text in fonts.items():
        (args.assets / f"face_font_{size}.c").write_text(text, encoding="utf-8", newline="\n")
    (args.assets / "face_icons.c").write_text(icons_c, encoding="ascii", newline="\n")
    (args.assets / "face_icons.h").write_text(icons_h, encoding="ascii", newline="\n")
    args.metrics.parent.mkdir(parents=True, exist_ok=True)
    args.metrics.write_text(metrics_text(metrics), encoding="ascii", newline="\n")
    logger.info("wrote the fonts and icons in %s and the metrics in %s", args.assets, args.metrics)


if __name__ == "__main__":
    main()
