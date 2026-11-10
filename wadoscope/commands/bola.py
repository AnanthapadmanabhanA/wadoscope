"""bola — test per-object authorization on a StudyInstanceUID (IDOR/BOLA)."""
from __future__ import annotations

import argparse
import sys

import wadoscope.logger as logger
from wadoscope.version import BANNER
from wadoscope.web.client import DicomWebClient
from wadoscope.checks.bola import check_bola
from wadoscope.commands._common import add_common_args, target_from_args, start_logging


def main(argv: list[str] | None = None) -> None:
    print(BANNER, file=sys.stderr)
    p = argparse.ArgumentParser(
        prog="wadoscope bola",
        description="Attempt to read a study's metadata by UID with the current "
                    "principal. Supply a UID the principal should NOT see.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_args(p)
    p.add_argument("--study", metavar="UID", required=True,
                   help="target StudyInstanceUID")

    options = p.parse_args(argv)
    start_logging(options)
    try:
        target = target_from_args(options)
    except ValueError as exc:
        logger.LOG.error(str(exc))
        sys.exit(2)

    with DicomWebClient(target, safe_mode=True) as client:
        try:
            f = check_bola(client, options.study)
        except Exception as exc:  # noqa: BLE001
            logger.LOG.error(f"BOLA check failed: {exc}")
            sys.exit(1)

    line = f"study={f.study_uid}  HTTP {f.status}"
    if f.accessible:
        logger.LOG.warning(f"[{f.severity.upper()}] {line} — {f.detail}")
    else:
        logger.LOG.info(f"{line} — {f.detail}")
    sys.exit(0)
