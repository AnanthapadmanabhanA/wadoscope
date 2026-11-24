"""CLI-level tests for the top-level dispatcher (the --version flag)."""
from __future__ import annotations

import subprocess
import sys

from wadoscope.version import __version__


def test_version_flag_prints_version():
    r = subprocess.run([sys.executable, "-m", "wadoscope", "--version"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "wadoscope" in r.stdout.lower()
    assert __version__ in r.stdout


def test_short_version_flag():
    r = subprocess.run([sys.executable, "-m", "wadoscope", "-V"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert __version__ in r.stdout
