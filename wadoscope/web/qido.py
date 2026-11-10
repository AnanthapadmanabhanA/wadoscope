"""QIDO-RS — query studies / series / instances over HTTP.

The URL/param builders are pure functions so they can be unit-tested without a
live server.  DICOM+JSON responses are flattened to plain dicts for display.
"""
from __future__ import annotations

from typing import Any, Optional

from .client import DicomWebClient

# ── pure URL builders ──────────────────────────────────────────────────────────

def studies_path() -> str:
    return "/studies"


def series_path(study_uid: str) -> str:
    return f"/studies/{study_uid}/series"


def instances_path(study_uid: str, series_uid: str) -> str:
    return f"/studies/{study_uid}/series/{series_uid}/instances"


def build_params(filters: Optional[dict[str, str]] = None,
                 limit: Optional[int] = None,
                 includefield: str = "all") -> dict[str, str]:
    """QIDO query params.  `includefield=all` asks the server for every field."""
    params: dict[str, str] = {}
    if includefield:
        params["includefield"] = includefield
    if limit is not None:
        params["limit"] = str(limit)
    for k, v in (filters or {}).items():
        params[k] = v
    return params


# ── DICOM+JSON flattening ───────────────────────────────────────────────────────
# Minimal tag -> keyword map for human-readable output.
TAGS = {
    "00100010": "PatientName",
    "00100020": "PatientID",
    "00100030": "PatientBirthDate",
    "00080020": "StudyDate",
    "00080060": "Modality",
    "00080061": "ModalitiesInStudy",
    "00080050": "AccessionNumber",
    "00081030": "StudyDescription",
    "0020000D": "StudyInstanceUID",
    "0020000E": "SeriesInstanceUID",
    "00200011": "SeriesNumber",
    "0008103E": "SeriesDescription",
    "00080018": "SOPInstanceUID",
    "00200013": "InstanceNumber",
}


def flatten(ds: dict[str, Any]) -> dict[str, str]:
    """Turn one DICOM+JSON object into {keyword: value}."""
    out: dict[str, str] = {}
    for tag, keyword in TAGS.items():
        node = ds.get(tag)
        if not node:
            continue
        values = node.get("Value")
        if not values:
            continue
        v = values[0]
        if isinstance(v, dict):                 # Person Name -> {"Alphabetic": "..."}
            v = v.get("Alphabetic", "")
        out[keyword] = str(v)
    return out


# ── search helpers ────────────────────────────────────────────────────────────

def _query(client: DicomWebClient, path: str, params: dict) -> list[dict[str, str]]:
    resp = client.get_json(path, params=params)
    if resp.status_code == 204:                 # no content
        return []
    resp.raise_for_status()
    ctype = resp.headers.get("content-type", "")
    if "json" not in ctype:
        return []
    return [flatten(obj) for obj in resp.json()]


def search_studies(client: DicomWebClient, filters: Optional[dict] = None,
                   limit: Optional[int] = None) -> list[dict[str, str]]:
    return _query(client, studies_path(), build_params(filters, limit))


def search_series(client: DicomWebClient, study_uid: str,
                  limit: Optional[int] = None) -> list[dict[str, str]]:
    return _query(client, series_path(study_uid), build_params(None, limit))


def search_instances(client: DicomWebClient, study_uid: str, series_uid: str,
                     limit: Optional[int] = None) -> list[dict[str, str]]:
    return _query(client, instances_path(study_uid, series_uid), build_params(None, limit))
