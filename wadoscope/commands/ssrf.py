"""ssrf — out-of-band SSRF probe of DICOMweb retrieve sinks (read-only)."""
from __future__ import annotations

import argparse
import sys

import wadoscope.logger as logger
from wadoscope import report
from wadoscope.version import BANNER
from wadoscope.web.client import DicomWebClient
from wadoscope.checks.ssrf import (
    CallbackServer, check_ssrf, SINK_PARAMS, PROBE_PATHS, build_probes,
)
from wadoscope.commands._common import add_common_args, target_from_args, start_logging


def _parse_listen(spec: str) -> tuple[str, int]:
    host, _, port = spec.rpartition(":")
    if not host or not port.isdigit():
        raise ValueError("--listen must be HOST:PORT, e.g. 127.0.0.1:8056")
    return host, int(port)


def main(argv: list[str] | None = None) -> None:
    print(BANNER, file=sys.stderr)
    p = argparse.ArgumentParser(
        prog="wadoscope ssrf",
        description="Probe DICOMweb retrieve endpoints for SSRF by spraying "
                    "candidate URL parameters with an out-of-band callback URL. "
                    "Read-only (GET) — no --unsafe needed.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_args(p)
    s = p.add_argument_group("ssrf")
    s.add_argument("--listen", default="127.0.0.1:8056", metavar="HOST:PORT",
                   help="bind the local callback listener here (default 127.0.0.1:8056)")
    s.add_argument("--callback", metavar="URL",
                   help="use an external collaborator URL instead of the local "
                        "listener (you watch it for the token yourself)")
    s.add_argument("--path", action="append", metavar="PATH",
                   help=f"retrieve endpoint(s) to probe (default: {PROBE_PATHS})")
    s.add_argument("--param", action="append", metavar="NAME",
                   help="sink parameter name(s) to spray (default: built-in list)")
    s.add_argument("--wait", type=float, default=4.0,
                   help="seconds to wait for callbacks (default 4)")
    o = p.add_argument_group("output")
    o.add_argument("--format", choices=["table", "csv", "json"], default="table")

    options = p.parse_args(argv)
    start_logging(options)
    try:
        target = target_from_args(options)
    except ValueError as exc:
        logger.LOG.error(str(exc))
        sys.exit(2)

    paths = options.path or list(PROBE_PATHS)
    params = options.param or list(SINK_PARAMS)

    # external collaborator mode: send probes, can't auto-confirm
    if options.callback:
        with DicomWebClient(target, safe_mode=True) as client:
            try:
                res = check_ssrf(client, callback_base=options.callback,
                                 paths=paths, params=params, wait=0.0)
            except Exception as exc:  # noqa: BLE001
                logger.LOG.error(f"SSRF probe failed: {exc}")
                sys.exit(1)
        logger.LOG.info(
            f"sent {res.probes_sent} probe(s) to {options.callback} "
            f"(token {res.token}). Watch your collaborator for a hit containing "
            f"'{res.token}-<param>' — the <param> names the vulnerable sink.")
        sys.exit(0)

    # local listener mode: auto-confirm
    try:
        host, port = _parse_listen(options.listen)
    except ValueError as exc:
        logger.LOG.error(str(exc))
        sys.exit(2)

    try:
        listener = CallbackServer(host, port).start()
    except OSError as exc:
        logger.LOG.error(f"cannot bind callback listener on {options.listen}: {exc}")
        sys.exit(1)

    logger.LOG.info(f"callback listener up on {listener.base_url}  "
                    f"({len(paths) * len(params)} probes)")
    try:
        with DicomWebClient(target, safe_mode=True) as client:
            res = check_ssrf(client, listener=listener,
                             paths=paths, params=params, wait=options.wait)
    except Exception as exc:  # noqa: BLE001
        logger.LOG.error(f"SSRF probe failed: {exc}")
        sys.exit(1)
    finally:
        listener.stop()

    if not res.findings:
        logger.LOG.info(f"sent {res.probes_sent} probe(s); no callback received "
                        f"— no SSRF confirmed on the probed sinks.")
        sys.exit(0)

    rows = [{"sink_param": f.sink, "severity": f.severity, "detail": f.detail}
            for f in res.findings]
    report.emit(rows, fmt=options.format,
                columns=["sink_param", "severity", "detail"])
    logger.LOG.warning(
        f"[HIGH] SSRF confirmed via: {', '.join(f.sink for f in res.findings)} "
        f"— the server made an outbound request to an attacker-controlled URL.")
    sys.exit(0)
