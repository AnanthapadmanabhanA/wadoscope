"""query — QIDO-RS enumeration of studies / series / instances.

The HTTP analog of a C-FIND tree walk: tests whether a DICOMweb endpoint
returns patient data to the current (possibly unauthenticated) principal.
"""
from __future__ import annotations

import argparse
import sys

import wadoscope.logger as logger
from wadoscope.version import BANNER
from wadoscope import report
from wadoscope.web.client import DicomWebClient
from wadoscope.web import qido
from wadoscope.commands._common import add_common_args, target_from_args, start_logging


def main(argv: list[str] | None = None) -> None:
    print(BANNER, file=sys.stderr)
    p = argparse.ArgumentParser(
        prog="wadoscope query",
        description="QIDO-RS query (studies/series/instances).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_args(p)
    q = p.add_argument_group("query")
    q.add_argument("--level", choices=["studies", "series", "instances"],
                   default="studies")
    q.add_argument("--study", metavar="UID", help="StudyInstanceUID (series/instances)")
    q.add_argument("--series", metavar="UID", help="SeriesInstanceUID (instances)")
    q.add_argument("-f", "--filter", action="append", default=[], metavar="KEY=VAL",
                   help="QIDO filter, repeatable (e.g. -f PatientID=123)")
    q.add_argument("--limit", type=int, default=0, help="max results (0=server default)")
    o = p.add_argument_group("output")
    o.add_argument("--format", choices=["table", "csv", "json"], default="table")
    o.add_argument("-o", "--output", metavar="FILE")

    options = p.parse_args(argv)
    start_logging(options)
    try:
        target = target_from_args(options)
    except ValueError as exc:
        logger.LOG.error(str(exc))
        sys.exit(2)

    filters = {}
    for item in options.filter:
        if "=" in item:
            k, v = item.split("=", 1)
            filters[k] = v
    limit = options.limit or None

    logger.LOG.info(f"Target: {target.base_url}  level={options.level}")
    with DicomWebClient(target, safe_mode=True) as client:
        try:
            if options.level == "studies":
                rows = qido.search_studies(client, filters, limit)
            elif options.level == "series":
                if not options.study:
                    logger.LOG.error("--study UID required for level=series")
                    sys.exit(2)
                rows = qido.search_series(client, options.study, limit)
            else:
                if not (options.study and options.series):
                    logger.LOG.error("--study and --series required for level=instances")
                    sys.exit(2)
                rows = qido.search_instances(client, options.study, options.series, limit)
        except Exception as exc:  # noqa: BLE001 — surface HTTP/parse errors to the operator
            logger.LOG.error(f"Query failed: {exc}")
            sys.exit(1)

    if not rows:
        logger.LOG.warning("No results (empty, denied, or non-JSON response).")
        sys.exit(0)

    logger.LOG.success(f"{len(rows)} result(s)")  # type: ignore[attr-defined]
    report.emit(rows, fmt=options.format, out_file=options.output)
    sys.exit(0)
