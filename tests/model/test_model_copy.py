"""Tests for the copy of the toolbox's model file in tests/model/.

`make hash` hashes the copy, so the commit checks need no toolbox. These tests
need the toolbox, so they run in the reference venv.

    reference/.venv/bin/python -m pytest tests/model -q

Nothing loads the copy as a model.
"""
from __future__ import annotations

import ast
import hashlib
import re
from importlib import metadata
from pathlib import Path

import paradigma

REPO = Path(__file__).resolve().parents[2]
MODEL_COPY = REPO / "tests" / "model" / "tremor_detection_clf_package.pkl"
LICENSE_COPY = REPO / "tests" / "model" / "LICENSE"
GEN_TABLES = REPO / "tools" / "gen_tables.py"
TABLES = REPO / "core" / "detector_tables.h"


def toolbox_model() -> Path:
    """Give the path of the model file in the installed paradigma package."""
    return Path(paradigma.__file__).resolve().parent / "assets" / "tremor_detection_clf_package.pkl"


def toolbox_license() -> Path:
    """Give the path of the licence in the paradigma-1.1.2 dist-info folder."""
    dist = metadata.distribution("paradigma")
    assert dist.version == "1.1.2"
    path = Path(str(dist.locate_file(f"paradigma-{dist.version}.dist-info/licenses/LICENSE")))
    return path.resolve()


def expected_in_gen_tables() -> str:
    """Give the value of EXPECTED_SHA256 in tools/gen_tables.py."""
    tree = ast.parse(GEN_TABLES.read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "EXPECTED_SHA256" in names and isinstance(node.value, ast.Constant):
                return str(node.value.value)
    raise AssertionError("tools/gen_tables.py has no EXPECTED_SHA256")


def expected_in_tables() -> str:
    """Give the value of DET_MODEL_SHA256 in core/detector_tables.h."""
    match = re.search(r'^#define DET_MODEL_SHA256 "([0-9a-f]{64})"$', TABLES.read_text(), re.M)
    assert match is not None, "core/detector_tables.h has no DET_MODEL_SHA256 line"
    return match.group(1)


def test_copies_match_the_toolbox() -> None:
    """Both copies match the installed files byte for byte."""
    assert MODEL_COPY.read_bytes() == toolbox_model().read_bytes()
    assert LICENSE_COPY.read_bytes() == toolbox_license().read_bytes()


def test_copy_hash_matches_the_tables() -> None:
    """The copy's SHA-256 hash matches both stored values."""
    digest = hashlib.sha256(MODEL_COPY.read_bytes()).hexdigest()
    assert digest == expected_in_gen_tables()
    assert digest == expected_in_tables()
