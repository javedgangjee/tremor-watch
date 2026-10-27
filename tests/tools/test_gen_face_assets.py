"""Tests for tools/gen_face_assets.py and the files it made.

They run in the reference venv with this command.

    reference/.venv/bin/python -m pytest tests/tools/test_gen_face_assets.py -q
"""
from __future__ import annotations

import ast
import importlib.util
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import numpy as np

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "tools" / "gen_face_assets.py"
ASSETS = REPO / "firmware" / "main" / "assets"
METRICS = REPO / "core" / "face_metrics.h"


def load_gen() -> ModuleType:
    """Load the tool as a module."""
    spec = importlib.util.spec_from_file_location("gen_face_assets", GEN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["gen_face_assets"] = module
    spec.loader.exec_module(module)
    return module


gen = load_gen()


def test_case_41_line_at_24_pixels() -> None:
    """The path M5 12h14 at 24 pixels with a stroke of 2."""
    img = gen.draw_icon([("path", "M5 12h14")], 24, 2.0)
    for row in (11, 12):
        assert all(img[row, col] == 255 for col in range(5, 19))
        assert img[row, 4] == 202
        assert img[row, 19] == 202
        assert img[row, 3] == 0
        assert img[row, 20] == 0
    assert not img[10].any()
    assert not img[13].any()


def test_case_42_line_at_88_pixels() -> None:
    """The same path at 88 pixels with a stroke of 5.5."""
    img = gen.draw_icon([("path", "M5 12h14")], 88, 5.5)
    for row in range(42, 46):
        assert img[row, 44] == 255
    assert img[41, 44] == 191
    assert img[46, 44] == 191
    assert img[40, 44] == 0
    assert img[47, 44] == 0


def test_case_43_circle() -> None:
    """A circle at (12, 12) with radius 10 at 24 pixels with a stroke of 2."""
    img = gen.draw_icon([("circle", 12.0, 12.0, 10.0)], 24, 2.0)
    assert img[2, 12] == 255
    assert img[12, 12] == 0


def test_case_44_arc_and_numbers() -> None:
    """The ring of circle-check-big lies on its circle, and compact arc numbers read right."""
    lines = gen.path_points("M21.801 10A10 10 0 1 1 17 3.335")
    points = [p for line in lines for p in line]
    assert len(points) > 2
    for x, y in points:
        assert abs(math.dist((x, y), (12.0, 12.0)) - 10.0) <= 0.01
    assert gen.parse_path("a.25.25 0 0 1-.48 0") == [("a", [0.25, 0.25, 0.0, 0.0, 1.0, -0.48, 0.0])]


def test_case_45_image_text() -> None:
    """write_image_c() of a 2 by 2 image."""
    text = gen.write_image_c("tiny", np.array([[0, 128], [255, 1]], dtype=np.uint8))
    assert "LV_COLOR_FORMAT_A8" in text
    assert re.search(r"\.w = 2\b", text)
    assert re.search(r"\.h = 2\b", text)
    assert re.search(r"\.stride = 2\b", text)
    assert re.search(r"\.data_size = 4\b", text)
    assert re.search(r"0x00, 0x80, 0xff, 0x01", text)


FONT_TEXT = """
static const lv_font_fmt_txt_glyph_dsc_t glyph_dsc[] = {
    {.bitmap_index = 0, .adv_w = 0, .box_w = 0, .box_h = 0, .ofs_x = 0, .ofs_y = 0} /* id = 0 reserved */,
    {.bitmap_index = 0, .adv_w = 64, .box_w = 0, .box_h = 0, .ofs_x = 0, .ofs_y = 0},
    {.bitmap_index = 0, .adv_w = 128, .box_w = 3, .box_h = 9, .ofs_x = 1, .ofs_y = 0},
    {.bitmap_index = 9, .adv_w = 200, .box_w = 5, .box_h = 4, .ofs_x = 1, .ofs_y = 5}
};
%UNICODE%
static const lv_font_fmt_txt_cmap_t cmaps[] =
{
    {
        .range_start = 32, .range_length = %LENGTH%, .glyph_id_start = 1,
        .unicode_list = %LIST%, .glyph_id_ofs_list = NULL, .list_length = %LISTLEN%, .type = %TYPE%
    }
};
const lv_font_t made_up = {
    .line_height = 30,          /*The maximum line height required by the font*/
    .base_line = 6,             /*Baseline measured from the bottom of the line*/
};
"""


def test_case_46_parse_font_output() -> None:
    """A made-up font output with a plain cmap and with a sparse cmap."""
    plain = (FONT_TEXT.replace("%UNICODE%", "").replace("%LENGTH%", "3").replace("%LIST%", "NULL")
             .replace("%LISTLEN%", "0").replace("%TYPE%", "LV_FONT_FMT_TXT_CMAP_FORMAT0_TINY"))
    m = gen.parse_font_output(plain)
    assert m.line_height == 30
    assert m.base_line == 6
    assert m.widths[0:3] == [4, 8, 13]
    assert m.widths[ord("#") - 32] == 0
    assert len(m.widths) == 95

    sparse = (FONT_TEXT.replace("%UNICODE%", "static const uint16_t unicode_list_0[] = {\n    0x0, 0xd, 0x10\n};")
              .replace("%LENGTH%", "17").replace("%LIST%", "unicode_list_0").replace("%LISTLEN%", "3")
              .replace("%TYPE%", "LV_FONT_FMT_TXT_CMAP_SPARSE_TINY"))
    m = gen.parse_font_output(sparse)
    assert m.widths[ord(" ") - 32] == 4
    assert m.widths[ord("-") - 32] == 8
    assert m.widths[ord("0") - 32] == 13
    assert m.widths[ord("!") - 32] == 0


def test_case_47_changed_font_writes_nothing(tmp_path: Path) -> None:
    """A font copy with one byte changed stops the run before any file is written."""
    font = tmp_path / "font.ttf"
    shutil.copyfile(ASSETS / "RedHatDisplay-Bold.ttf", font)
    data = bytearray(font.read_bytes())
    data[1000] ^= 0xFF
    font.write_bytes(bytes(data))
    assets = tmp_path / "assets"
    metrics = tmp_path / "metrics" / "face_metrics.h"
    run = subprocess.run(
        [sys.executable, str(GEN), "--font", str(font), "--assets", str(assets), "--metrics", str(metrics)],
        capture_output=True, text=True, check=False)
    assert run.returncode == 1
    assert not assets.exists() or not any(assets.iterdir())
    assert not metrics.exists()


def metrics_array(text: str, size: int) -> list[int]:
    """Return the committed advance widths at one size."""
    match = re.search(r"face_adv_" + str(size) + r"\[95\] = \{(.*?)\};", text, re.S)
    assert match is not None
    return [int(v) for v in re.findall(r"\d+", match.group(1))]


def define(text: str, name: str) -> int:
    """Return the value of one #define in the committed metrics."""
    match = re.search(r"#define " + name + r" (\d+)", text)
    assert match is not None
    return int(match.group(1))


def test_case_48_committed_files() -> None:
    """The committed metrics and the options line of each font file."""
    text = METRICS.read_text(encoding="ascii")
    for size in (28, 40, 56):
        widths = metrics_array(text, size)
        assert len(widths) == 95
        assert all(w > 0 for w in widths[1:])
    widths = metrics_array(text, 96)
    for ch in "0123456789:-":
        assert widths[ord(ch) - 32] > 0
    assert widths[ord("A") - 32] == 0
    assert define(text, "FACE_LINE_28") < define(text, "FACE_LINE_40") < define(text, "FACE_LINE_56")
    ranges = {28: "0x20-0x7E", 40: "0x20-0x7E", 56: "0x20-0x7E", 96: "0x20,0x2D,0x30-0x3A"}
    for size, chars in ranges.items():
        font_text = (ASSETS / f"face_font_{size}.c").read_text(encoding="utf-8")
        opts = re.search(r"^ \* Opts: (.*)$", font_text, re.M)
        assert opts is not None
        line = opts.group(1)
        assert "--bpp 4" in line
        assert "--no-kerning" in line
        assert f"--size {size}" in line
        assert f"-r {chars}" in line


def functions_of(path: Path) -> list[ast.FunctionDef]:
    """Return every function in a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def test_case_49_style() -> None:
    """Type hints everywhere, and no print, os.path, or except Exception in the tool."""
    for path in (GEN, Path(__file__)):
        for fn in functions_of(path):
            args = fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs
            for arg in args:
                assert arg.annotation is not None, f"{path.name}: {fn.name}({arg.arg}) has no type hint"
            assert fn.returns is not None, f"{path.name}: {fn.name} has no return hint"
    source = GEN.read_text(encoding="utf-8")
    assert "print(" not in source
    assert "os.path" not in source
    assert "except Exception" not in source
