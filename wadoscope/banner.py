"""Startup banner: a coloured ANSI wordmark with an optional scan animation.

Design rules (so the banner never breaks real use):
  * always printed to **stderr** — stdout stays clean for piped results
    (`--format json`, `-o file.csv`, `| jq`, ...);
  * colour only on an interactive terminal, and never when ``NO_COLOR`` is set;
  * the wipe-down "scan" animation only runs on an interactive TTY;
  * piped / redirected / CI runs get a single compact line instead of the big
    art, to keep logs tidy;
  * fully silenced with ``--no-banner`` or ``WADOSCOPE_NO_BANNER=1``.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

from .version import __version__, BANNER
from .banner_art import WORDMARK_LINES

# xterm-256 vertical ramp: bright cyan -> deep blue (a "scope" glow)
_RAMP = [51, 45, 39, 33, 27, 21]
_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"
_AMBER = "\x1b[38;5;220m"
_CYAN = "\x1b[38;5;51m"

_TAGLINE = "DICOMweb offensive toolkit"
_SERVICES = "discover · query · retrieve · store · cors · bola · ssrf · xss"
_WARN = "authorized testing only"


def _flag_off() -> bool:
    return bool(os.environ.get("WADOSCOPE_NO_BANNER")) or "--no-banner" in sys.argv


def _is_tty(stream) -> bool:
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def _want_color(stream) -> bool:
    if os.environ.get("NO_COLOR") or os.environ.get("WADOSCOPE_NO_COLOR"):
        return False
    if not _is_tty(stream):
        return False
    try:                                    # make ANSI work on Windows terminals
        import colorama
        colorama.just_fix_windows_console()
    except Exception:
        pass
    return True


def _paint(text: str, code: int, color: bool, bold: bool = False) -> str:
    if not color:
        return text
    pre = (_BOLD if bold else "") + f"\x1b[38;5;{code}m"
    return f"{pre}{text}{_RESET}"


def show(stream=None, animate: Optional[bool] = None) -> None:
    """Print the startup banner. Safe to call unconditionally."""
    if _flag_off():
        return
    stream = stream if stream is not None else sys.stderr

    # non-interactive (pipe / redirect / CI): one tidy line, no art, no colour.
    if not _is_tty(stream):
        print(BANNER, file=stream)
        return

    try:
        color = _want_color(stream)
        help_req = any(a in ("-h", "--help") for a in sys.argv)
        if animate is None:
            animate = not help_req
        step = 0.035 if animate else 0.0

        stream.write("\n")
        for row, line in zip(WORDMARK_LINES, _RAMP):
            stream.write(_paint(row, line, color) + "\n")
            stream.flush()
            if step:
                time.sleep(step)

        scope = _paint("◎", 51, color, bold=True)
        tag = _paint(f"{_TAGLINE} · v{__version__}", 51, color, bold=True)
        services = f"{_DIM}{_SERVICES}{_RESET}" if color else _SERVICES
        warn = f"{_AMBER}⚠ {_WARN}{_RESET}" if color else f"⚠ {_WARN}"

        stream.write(f"  {scope} {tag}\n")
        stream.write(f"    {services}\n")
        stream.write(f"    {warn}\n\n")
        stream.flush()
    except Exception:
        # never let the banner break a command
        try:
            print(BANNER, file=stream)
        except Exception:
            pass
