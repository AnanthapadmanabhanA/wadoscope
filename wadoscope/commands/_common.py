"""Shared argparse wiring for commands (keeps each command file tiny)."""
from __future__ import annotations

import argparse

import wadoscope.logger as logger
from wadoscope.target import WebTarget, parse_web_target


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        help="DICOMweb base URL, e.g. https://pacs:8042/dicom-web",
    )
    auth = parser.add_argument_group("auth")
    auth.add_argument("--basic", metavar="USER:PASS", help="HTTP basic auth")
    auth.add_argument("--bearer", metavar="TOKEN", help="OAuth2 / SMART bearer token")

    conn = parser.add_argument_group("connection")
    conn.add_argument("-k", "--insecure", action="store_true",
                      help="skip TLS certificate verification")
    conn.add_argument("-t", "--timeout", type=float, default=30.0, metavar="SECS")

    log = parser.add_argument_group("logging")
    log.add_argument("-d", "--debug", action="store_true")
    log.add_argument("--ts", action="store_true", help="timestamps in log output")
    log.add_argument("--no-banner", action="store_true",
                     help="suppress the startup banner (also: WADOSCOPE_NO_BANNER=1)")


def target_from_args(options) -> WebTarget:
    username = password = token = ""
    if getattr(options, "basic", None):
        if ":" not in options.basic:
            raise ValueError("--basic must be in the form USER:PASS")
        username, password = options.basic.split(":", 1)
    if getattr(options, "bearer", None):
        token = options.bearer
    return parse_web_target(
        options.target,
        username=username,
        password=password,
        token=token,
        verify_tls=not options.insecure,
        timeout=options.timeout,
    )


def start_logging(options) -> None:
    logger.init(timestamps=options.ts, debug=options.debug)
