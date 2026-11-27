"""Unit tests for the report renderer (render / emit): pure, no network.

Covers the format branches (table / csv / json), column selection, the
missing-cell and extra-key handling, and emit's stdout-vs-file split.
"""
from __future__ import annotations

import csv
import json
from io import StringIO

from wadoscope.report import emit, render

ROWS = [
    {"base_url": "http://h/dicom-web", "status": 200, "auth": False},
    {"base_url": "http://h/qido-rs", "status": 401, "auth": True},
]


def test_empty_rows_render_to_empty_string():
    assert render([]) == ""
    assert render([], fmt="json") == ""
    assert render([], fmt="csv") == ""


def test_json_round_trips_all_rows():
    out = render(ROWS, fmt="json")
    assert json.loads(out) == ROWS


def test_json_ignores_columns_and_stringifies_non_serialisable():
    # json dumps whole row dicts; `columns` does not prune them, and
    # default=str keeps a non-JSON value (a set) from blowing up.
    out = render([{"a": 1, "b": {2, 3}}], fmt="json", columns=["a"])
    parsed = json.loads(out)
    assert set(parsed[0].keys()) == {"a", "b"}
    assert isinstance(parsed[0]["b"], str)


def test_csv_has_header_and_one_line_per_row():
    out = render(ROWS, fmt="csv")
    reader = list(csv.DictReader(StringIO(out)))
    assert len(reader) == 2
    assert reader[0]["base_url"] == "http://h/dicom-web"
    assert reader[1]["status"] == "401"


def test_csv_respects_column_selection_and_drops_extra_keys():
    out = render([{"a": 1, "b": 2, "c": 3}], fmt="csv", columns=["a", "b"])
    rows = list(csv.reader(StringIO(out)))
    assert rows[0] == ["a", "b"]        # header is exactly the chosen columns
    assert rows[1] == ["1", "2"]        # extra key `c` is ignored, not an error


def test_csv_fills_missing_cell_with_empty():
    out = render([{"a": 1}], fmt="csv", columns=["a", "b"])
    rows = list(csv.reader(StringIO(out)))
    assert rows[1] == ["1", ""]


def test_table_defaults_columns_to_first_row_keys():
    out = render([{"a": 1, "b": 2}], fmt="table")
    assert "a" in out and "b" in out
    assert "1" in out and "2" in out


def test_table_fills_missing_cell_without_error():
    # second row lacks `b`; render must not raise and must still show `a`.
    out = render([{"a": 1, "b": 2}, {"a": 3}], fmt="table")
    assert "3" in out


def test_unknown_format_falls_through_to_table():
    # Any fmt that is not json/csv renders as the table branch.
    assert render([{"a": 1}], fmt="nonsense") == render([{"a": 1}], fmt="table")


def test_emit_prints_to_stdout_by_default(capsys):
    emit([{"a": 1}], fmt="csv")
    captured = capsys.readouterr()
    assert "a" in captured.out


def test_emit_writes_to_file_when_out_file_given(tmp_path, capsys):
    target = tmp_path / "out.csv"
    emit(ROWS, fmt="csv", out_file=str(target))
    captured = capsys.readouterr()
    assert captured.out == ""                      # nothing printed
    # read_text() normalises line endings, so compare parsed content, not bytes.
    reader = list(csv.DictReader(StringIO(target.read_text())))
    assert [r["base_url"] for r in reader] == [r["base_url"] for r in ROWS]
