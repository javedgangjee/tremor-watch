"""Shared pytest setup for tests/.

Several tests run the laptop build of replay at build/core/replay. Before any
test runs, this file brings that build up to date, so a test never checks an
old binary after a change in core/. With no build/ folder it does nothing, and
the tests that need replay fail as they would without it.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

LOG = logging.getLogger("conftest")

REPO = Path(__file__).resolve().parents[1]
BUILD = REPO / "build"


def pytest_sessionstart(session: pytest.Session) -> None:
    """Rebuild replay when the laptop build exists."""
    if not (BUILD / "CMakeCache.txt").exists():
        LOG.warning("no laptop build in %s, so replay is not rebuilt", BUILD)
        return
    subprocess.run(["cmake", "--build", str(BUILD), "--target", "replay"], check=True, capture_output=True)
