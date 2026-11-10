"""xss — stored-XSS-in-metadata check (STOW a scripted tag, read it back).

WRITE operation: stores one synthetic instance, so it requires --unsafe.
"""
from __future__ import annotations

import argparse
import sys

import wadoscope.logger as logger
from wadoscope import report
from wadoscope.version import BANNER
from wadoscope.web.client import DicomWebClient, SafeModeError
from wadoscope.checks.xss import check_xss, DEFAULT_PAYLOAD, PAYLOADS, TAG_HEX
from wadoscope.commands._common import add_common_args, target_from_args, start_logging


def main(argv: list[str] | None = None) -> None:
    print(BANNER, file=sys.stderr)
    p = argparse.ArgumentParser(
        prog="wadoscope xss",
        description="Store an instance whose free-text tags carry an XSS payload, "
                    "then check whether the server returns it unsanitised over "
                    "WADO-RS. WRITE operation — requires --unsafe.",
        epilog="Prove execution with the lab viewer:  docker/xss_viewer.html\n"
               "Note: PatientName / ReferringPhysicianName are PN-VR, where '=' is "
               "a component separator — an 'onerror=' payload is truncated there. "
               "For those tags pass a '='-free payload, e.g.\n"
               "  --payload '<script>alert(document.domain)</script>'",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_args(p)
    x = p.add_argument_group("xss")
    x.add_argument("--payload", default=DEFAULT_PAYLOAD,
                   help=f"XSS payload to inject (default: {DEFAULT_PAYLOAD!r})")
    x.add_argument("--tags", metavar="KW", nargs="+", choices=sorted(TAG_HEX),
                   help="limit injection to these tags (default: all injectable)")
    x.add_argument("--list-payloads", action="store_true",
                   help="print the bundled payloads and exit")
    x.add_argument("--unsafe", action="store_true",
                   help="actually store the instance (off by default)")
    o = p.add_argument_group("output")
    o.add_argument("--format", choices=["table", "csv", "json"], default="table")

    options = p.parse_args(argv)
    start_logging(options)

    if options.list_payloads:
        for pl in PAYLOADS:
            print(pl)
        sys.exit(0)

    try:
        target = target_from_args(options)
    except ValueError as exc:
        logger.LOG.error(str(exc))
        sys.exit(2)

    with DicomWebClient(target, safe_mode=not options.unsafe) as client:
        try:
            res = check_xss(client, payload=options.payload, tags=options.tags)
        except SafeModeError as exc:
            logger.LOG.warning(str(exc))
            sys.exit(0)
        except ImportError:
            logger.LOG.error("This check needs pydicom:  pip install pydicom")
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            logger.LOG.error(f"XSS check failed: {exc}")
            sys.exit(1)

    logger.LOG.info(f"stored study {res.study_uid}  (STOW HTTP {res.stow_status})")
    if not res.findings:
        logger.LOG.warning("No injectable tags returned in metadata "
                           "(server stripped them, or retrieval failed).")
        sys.exit(0)

    rows = [{"tag": f.tag,
             "stored": f.stored,
             "unescaped": f.unescaped,
             "severity": f.severity,
             "returned": f.returned[:60],
             "detail": f.detail}
            for f in res.findings]
    report.emit(rows, fmt=options.format,
                columns=["tag", "stored", "unescaped", "severity", "returned", "detail"])

    if res.vulnerable_tags:
        logger.LOG.warning(
            f"[HIGH] payload stored UNESCAPED in: {', '.join(res.vulnerable_tags)} "
            f"— XSS-prone in any viewer that renders these tags as HTML. "
            f"Demo it: open docker/xss_viewer.html against this study."
        )
    else:
        logger.LOG.success(  # type: ignore[attr-defined]
            "Server sanitised / encoded every injected tag on readback.")
    sys.exit(0)
