"""webdiscover — find DICOMweb endpoints, fingerprint the server, and flag
whether /studies answers without authentication.
"""
from __future__ import annotations

import argparse
import sys

import wadoscope.logger as logger
from wadoscope import banner
from wadoscope.checks.discover import discover


def main(argv: list[str] | None = None) -> None:
    banner.show()
    p = argparse.ArgumentParser(
        prog="wadoscope discover",
        description="Probe common DICOMweb base paths; fingerprint server/cloud; "
                    "detect unauthenticated /studies access.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("target", help="root URL, e.g. https://pacs:8042 (base path auto-probed)")
    p.add_argument("-k", "--insecure", action="store_true", help="skip TLS verification")
    p.add_argument("-t", "--timeout", type=float, default=15.0, metavar="SECS")
    p.add_argument("-d", "--debug", action="store_true")
    p.add_argument("--ts", action="store_true")
    p.add_argument("--no-banner", action="store_true",
                   help="suppress the startup banner (also: WADOSCOPE_NO_BANNER=1)")
    options = p.parse_args(argv)
    logger.init(timestamps=options.ts, debug=options.debug)

    logger.LOG.info(f"Discovering DICOMweb under {options.target}")
    findings = discover(options.target, verify_tls=not options.insecure,
                        timeout=options.timeout)

    any_hit = False
    for f in findings:
        if not f.reachable:
            logger.LOG.debug(f"{f.base_url:<40} unreachable ({'; '.join(f.notes)})")
            continue
        any_hit = True
        line = f"{f.base_url:<40} HTTP {f.status}  [{f.product}]"
        if f.auth_enforced is True:
            logger.LOG.info(line + "  auth: enforced")
        elif f.auth_enforced is False:
            logger.LOG.success(line + "  auth: NONE")  # type: ignore[attr-defined]
            for n in f.notes:
                logger.LOG.warning("  " + n)
        else:
            logger.LOG.info(line)

    if not any_hit:
        logger.LOG.warning("No DICOMweb endpoints responded.")
        sys.exit(1)
    sys.exit(0)
