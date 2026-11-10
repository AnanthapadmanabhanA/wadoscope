"""Startup banner: a colourful ANSI wordmark with an optional scan animation.

Design rules (so the banner never breaks real use):
  * always printed to **stderr** — stdout stays clean for piped results
    (`--format json`, `-o file.csv`, `| jq`, ...);
  * colour only on an interactive terminal, and never when ``NO_COLOR`` is set;
  * 24-bit truecolour when the terminal advertises it (``COLORTERM``), else a
    256-colour fallback;
  * the wipe-down "scan" animation only runs on an interactive TTY;
  * piped / redirected / CI runs get a single compact line instead of the art;
  * fully silenced with ``--no-banner`` or ``WADOSCOPE_NO_BANNER=1``.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

from .version import __version__, BANNER
from .banner_art import WORDMARK_LINES

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"

# neon gradient stops, applied left-to-right across the wordmark
#   hot-pink -> violet -> blue -> cyan
STOPS = [(255, 60, 172), (168, 74, 255), (58, 150, 255), (46, 248, 214)]
ACCENT = (132, 236, 255)     # scope glyph + headline
WARN_RGB = (255, 178, 44)    # amber warning
# per-token hues for the command list
SERVICE_PALETTE = [
    (88, 255, 206), (120, 206, 255), (182, 150, 255), (255, 150, 200),
    (255, 214, 120), (130, 240, 170), (150, 200, 255), (255, 170, 230),
]

_WORD_W = max(len(l) for l in WORDMARK_LINES)
_TAGLINE = "DICOMweb offensive toolkit"
_SERVICES = ["discover", "query", "retrieve", "store", "cors", "bola", "ssrf", "xss"]
_WARN = "authorized testing only"


def _flag_off() -> bool:
    return bool(os.environ.get("WADOSCOPE_NO_BANNER")) or "--no-banner" in sys.argv


def _is_tty(stream) -> bool:
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def _truecolor() -> bool:
    return os.environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")


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


def _fg(rgb) -> str:
    """Foreground escape: truecolour if available, else nearest xterm-256 cube."""
    r, g, b = rgb
    if _truecolor():
        return f"\x1b[38;2;{r};{g};{b}m"
    q = lambda v: round(v / 255 * 5)
    return f"\x1b[38;5;{16 + 36 * q(r) + 6 * q(g) + q(b)}m"


def _grad(t: float):
    """RGB at position t in [0,1] along STOPS."""
    if t <= 0:
        return STOPS[0]
    if t >= 1:
        return STOPS[-1]
    seg = t * (len(STOPS) - 1)
    i = int(seg)
    f = seg - i
    a, b = STOPS[i], STOPS[i + 1]
    return tuple(round(a[j] + (b[j] - a[j]) * f) for j in range(3))


def _grad_line(s: str, color: bool, width: int) -> str:
    """Colour *s* across the horizontal gradient by column index."""
    if not color:
        return s
    out, last = [], None
    span = max(width - 1, 1)
    for i, ch in enumerate(s):
        code = _fg(_grad(i / span))
        if code != last:
            out.append(code)
            last = code
        out.append(ch)
    out.append(_RESET)
    return "".join(out)


def _solid(s: str, rgb, color: bool, bold: bool = False) -> str:
    if not color:
        return s
    return (_BOLD if bold else "") + _fg(rgb) + s + _RESET


def _services(color: bool) -> str:
    sep = (_DIM + " · " + _RESET) if color else " · "
    toks = [_solid(n, SERVICE_PALETTE[i % len(SERVICE_PALETTE)], color)
            for i, n in enumerate(_SERVICES)]
    return sep.join(toks)


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
        for line in WORDMARK_LINES:
            stream.write(_grad_line(line, color, _WORD_W) + "\n")
            stream.flush()
            if step:
                time.sleep(step)
        stream.write(_grad_line("━" * _WORD_W, color, _WORD_W) + "\n")

        scope = _solid("◎", ACCENT, color, bold=True)
        head = _solid(_TAGLINE, ACCENT, color, bold=True)
        ver = (_DIM + f" · v{__version__}" + _RESET) if color else f" · v{__version__}"
        warn = _solid(f"⚠ {_WARN}", WARN_RGB, color)

        stream.write(f"  {scope} {head}{ver}\n")
        stream.write(f"    {_services(color)}\n")
        stream.write(f"    {warn}\n\n")
        stream.flush()
    except Exception:
        # never let the banner break a command
        try:
            print(BANNER, file=stream)
        except Exception:
            pass
