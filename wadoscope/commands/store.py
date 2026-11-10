"""store — STOW-RS injection (write). Blocked unless --unsafe is given."""
from __future__ import annotations

import argparse
import sys

import wadoscope.logger as logger
from wadoscope.version import BANNER
from wadoscope.web.client import DicomWebClient, SafeModeError
from wadoscope.web import stow
from wadoscope.commands._common import add_common_args, target_from_args, start_logging


def main(argv: list[str] | None = None) -> None:
    print(BANNER, file=sys.stderr)
    p = argparse.ArgumentParser(
        prog="wadoscope store",
        description="STOW-RS: upload DICOM instances. WRITE operation — requires --unsafe.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_args(p)
    s = p.add_argument_group("store")
    s.add_argument("paths", nargs="+", help="DICOM file(s) or director(y/ies) to upload")
    s.add_argument("--unsafe", action="store_true",
                   help="actually perform the write (off by default)")

    options = p.parse_args(argv)
    start_logging(options)
    try:
        target = target_from_args(options)
    except ValueError as exc:
        logger.LOG.error(str(exc))
        sys.exit(2)

    with DicomWebClient(target, safe_mode=not options.unsafe) as client:
        try:
            resp = stow.stow_store(client, options.paths)
        except SafeModeError as exc:
            logger.LOG.warning(str(exc))
            sys.exit(0)
        except Exception as exc:  # noqa: BLE001
            logger.LOG.error(f"STOW failed: {exc}")
            sys.exit(1)
    logger.LOG.success(f"STOW-RS status {resp.status_code}")  # type: ignore[attr-defined]
    if options.debug:
        logger.LOG.debug(resp.text[:2000])
    sys.exit(0)
