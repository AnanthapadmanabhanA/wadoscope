"""Tiny logging wrapper.

Usage:
    import wadoscope.logger as logger
    logger.init(timestamps=False, debug=False)
    logger.LOG.info("msg"); logger.LOG.success("ok"); logger.LOG.warning("..")
"""
import logging
import sys

try:                                   # colour is optional
    import colorama
    colorama.init()
    from colorama import Fore, Style
    _COLOR = True
except Exception:                      # pragma: no cover
    _COLOR = False

    class _Dummy:
        def __getattr__(self, _):      # every attribute -> ""
            return ""

    Fore = Style = _Dummy()

SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")


def _success(self, msg, *args, **kw):
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, msg, args, **kw)


logging.Logger.success = _success      # type: ignore[attr-defined]

LOG = logging.getLogger("wadoscope")

_LEVEL_COLOR = {
    "DEBUG":   Fore.CYAN,
    "INFO":    Fore.BLUE,
    "SUCCESS": Fore.GREEN,
    "WARNING": Fore.YELLOW,
    "ERROR":   Fore.RED,
    "CRITICAL": Fore.RED,
}


class _Formatter(logging.Formatter):
    def __init__(self, timestamps: bool):
        fmt = "%(asctime)s " if timestamps else ""
        fmt += "%(levelname_c)s %(message)s"
        super().__init__(fmt, datefmt="%H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        tag = f"[{record.levelname[:1]}]"
        if _COLOR:
            tag = f"{_LEVEL_COLOR.get(record.levelname, '')}{tag}{Style.RESET_ALL}"
        record.levelname_c = tag
        return super().format(record)


def init(timestamps: bool = False, debug: bool = False) -> None:
    LOG.handlers.clear()
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(_Formatter(timestamps))
    LOG.addHandler(h)
    LOG.setLevel(logging.DEBUG if debug else logging.INFO)
    LOG.propagate = False
