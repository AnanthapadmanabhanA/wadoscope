"""retrieve — WADO-RS metadata / study retrieval (exfiltration primitive)."""
from __future__ import annotations

import argparse
import os
import sys

import wadoscope.logger as logger
from wadoscope import banner
from wadoscope import report
from wadoscope.web.client import DicomWebClient
from wadoscope.web import wado, qido
from wadoscope.commands._common import add_common_args, target_from_args, start_logging


def main(argv: list[str] | None = None) -> None:
    banner.show()
    p = argparse.ArgumentParser(
        prog="wadoscope retrieve",
        description="WADO-RS: pull study/series metadata (read-only) or a full study.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_common_args(p)
    r = p.add_argument_group("retrieve")
    r.add_argument("--study", metavar="UID", required=True)
    r.add_argument("--series", metavar="UID", help="limit to one series (metadata)")
    r.add_argument("--mode", choices=["metadata", "study"], default="metadata",
                   help="metadata (JSON, read-only) or full study (saved to -o DIR)")
    r.add_argument("-o", "--output", metavar="DIR", default="./wadoscope_out")
    r.add_argument("--no-split", action="store_true",
                   help="save the raw multipart body instead of splitting into .dcm files")
    r.add_argument("--format", choices=["table", "csv", "json"], default="json")

    options = p.parse_args(argv)
    start_logging(options)
    try:
        target = target_from_args(options)
    except ValueError as exc:
        logger.LOG.error(str(exc))
        sys.exit(2)

    with DicomWebClient(target, safe_mode=True) as client:
        try:
            if options.mode == "metadata":
                meta = wado.retrieve_metadata(client, options.study, options.series)
                rows = [qido.flatten(m) for m in meta]
                if not rows:
                    logger.LOG.warning("No metadata returned.")
                    sys.exit(0)
                logger.LOG.success(f"{len(rows)} instance record(s)")  # type: ignore[attr-defined]
                report.emit(rows, fmt=options.format,
                            out_file=None if options.format != "json" else None)
            else:
                paths = wado.retrieve_study(client, options.study, options.output,
                                            split=not options.no_split)
                if len(paths) == 1 and paths[0].endswith(".multipart"):
                    logger.LOG.warning(f"Saved raw multipart body: {paths[0]}")
                else:
                    logger.LOG.success(  # type: ignore[attr-defined]
                        f"Saved {len(paths)} instance(s) to {options.output}/")
                    for pth in paths[:10]:
                        logger.LOG.info(f"  {os.path.basename(pth)}")
                    if len(paths) > 10:
                        logger.LOG.info(f"  ... and {len(paths) - 10} more")
        except Exception as exc:  # noqa: BLE001
            logger.LOG.error(f"Retrieve failed: {exc}")
            sys.exit(1)
    sys.exit(0)
