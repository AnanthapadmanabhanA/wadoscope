"""WADO-RS — retrieve studies / series / instances and their metadata.

Metadata retrieval (DICOM+JSON) is cheap and read-only; it is the primary
exfiltration primitive this tool exercises.  Bulk pixel retrieval writes the
raw multipart body to disk for later parsing.
"""
from __future__ import annotations

import os
from typing import Optional

from .client import DicomWebClient, DICOM_MULTIPART_ACCEPT


def study_metadata_path(study_uid: str) -> str:
    return f"/studies/{study_uid}/metadata"


def series_metadata_path(study_uid: str, series_uid: str) -> str:
    return f"/studies/{study_uid}/series/{series_uid}/metadata"


def study_path(study_uid: str) -> str:
    return f"/studies/{study_uid}"


def retrieve_metadata(client: DicomWebClient, study_uid: str,
                      series_uid: Optional[str] = None) -> list[dict]:
    """WADO-RS metadata (DICOM+JSON). Read-only; good for proving PHI exposure."""
    path = (series_metadata_path(study_uid, series_uid)
            if series_uid else study_metadata_path(study_uid))
    resp = client.get_json(path)
    if resp.status_code == 204:
        return []
    resp.raise_for_status()
    if "json" not in resp.headers.get("content-type", ""):
        return []
    return resp.json()


def retrieve_study(client: DicomWebClient, study_uid: str, out_dir: str) -> str:
    """Pull a whole study (multipart/related DICOM) and save the raw body.

    Returns the path written. Splitting the multipart into individual .dcm
    instances is left to v2 (kept simple here on purpose).
    """
    resp = client.get_raw(study_path(study_uid), accept=DICOM_MULTIPART_ACCEPT)
    resp.raise_for_status()
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, f"{study_uid}.multipart")
    with open(dest, "wb") as fh:
        fh.write(resp.content)
    return dest
