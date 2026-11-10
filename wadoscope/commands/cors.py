"""cors — check DICOMweb CORS policy for cross-origin PHI exposure."""
from __future__ import annotations

import argparse
import sys

import wadoscope.logger as logger
from wadoscope import banner
from wadoscope.web.client import DicomWebClient
from wadoscope.checks.cors import check_cors, PROBE_ORIGIN
from wadoscope.commands._common import add_common_args, target_from_args, start_logging


def main(argv: list[str] | None = None) -> None:
    banner.show()
    p = argparse.ArgumentParser(
        prog="wadoscope cors",
        description="Probe the CORS policy with a foreign Origin.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_args(p)
    p.add_argument("--origin", default=PROBE_ORIGIN, help="Origin header to send")

    options = p.parse_args(argv)
    start_logging(options)
    try:
        target = target_from_args(options)
    except ValueError as exc:
        logger.LOG.error(str(exc))
        sys.exit(2)

    with DicomWebClient(target, safe_mode=True) as client:
        try:
            f = check_cors(client, origin=options.origin)
        except Exception as exc:  # noqa: BLE001
            logger.LOG.error(f"CORS check failed: {exc}")
            sys.exit(1)

    logger.LOG.info(f"ACAO={f.acao!r}  allow_credentials={f.allow_credentials}")
    msg = f"[{f.severity.upper()}] {f.detail}"
    if f.severity in ("high", "medium"):
        logger.LOG.warning(msg)
    else:
        logger.LOG.info(msg)
    sys.exit(0)
