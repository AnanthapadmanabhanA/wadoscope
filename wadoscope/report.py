"""Tiny output helpers: render a list of row-dicts as a table / CSV / JSON."""
from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any, Optional

try:
    from tabulate import tabulate
    _HAS_TABULATE = True
except Exception:                       # pragma: no cover
    _HAS_TABULATE = False


def render(rows: list[dict[str, Any]], fmt: str = "table",
           columns: Optional[list[str]] = None) -> str:
    if not rows:
        return ""
    cols = columns or list(rows[0].keys())

    if fmt == "json":
        return json.dumps(rows, indent=2, default=str)

    if fmt == "csv":
        buf = StringIO()
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
        return buf.getvalue()

    # table
    table = [[r.get(c, "") for c in cols] for r in rows]
    if _HAS_TABULATE:
        return tabulate(table, headers=cols, tablefmt="simple")
    out = ["\t".join(cols)]
    out += ["\t".join(str(v) for v in row) for row in table]
    return "\n".join(out)


def emit(rows: list[dict[str, Any]], fmt: str = "table",
         columns: Optional[list[str]] = None, out_file: Optional[str] = None) -> None:
    text = render(rows, fmt, columns)
    if out_file:
        from pathlib import Path
        Path(out_file).write_text(text)
    else:
        print(text)
