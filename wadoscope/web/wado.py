"""WADO-RS — retrieve studies / series / instances and their metadata.

Metadata retrieval (DICOM+JSON) is cheap and read-only; it is the primary
exfiltration primitive this tool exercises.  Bulk pixel retrieval writes the
raw multipart body to disk for later parsing.
"""
from __future__ import annotations

import io
import os
import re
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


def _boundary(content_type: str) -> Optional[str]:
    """Pull the boundary token out of a multipart/related Content-Type."""
    m = re.search(r'boundary="?([^";]+)"?', content_type or "")
    return m.group(1).strip() if m else None


def _strip_headers(chunk: bytes) -> bytes:
    """Drop a MIME part's headers, returning the body that follows the blank line."""
    for sep in (b"\r\n\r\n", b"\n\n"):
        i = chunk.find(sep)
        if i != -1:
            return chunk[i + len(sep):]
    return chunk


def _strip_one_trailing_eol(body: bytes) -> bytes:
    """Remove the single CR/LF the encoding inserts before the next boundary.

    Only one is removed, so instance bytes that legitimately end in 0x0A/0x0D
    survive byte-for-byte.
    """
    if body.endswith(b"\r\n"):
        return body[:-2]
    if body.endswith(b"\n"):
        return body[:-1]
    return body


def split_multipart(body: bytes, content_type: str) -> list[bytes]:
    """Split a multipart/related response into its application/dicom parts.

    Pure function. Returns each part's raw bytes (a complete DICOM object,
    preamble included), in order, preserved byte-for-byte. Returns [] if the
    boundary can't be found.
    """
    boundary = _boundary(content_type)
    if not boundary:
        return []
    delim = b"--" + boundary.encode()
    out: list[bytes] = []
    for chunk in body.split(delim):
        if not chunk or chunk[:2] == b"--":      # preamble, or closing "--\r\n"
            continue
        payload = _strip_one_trailing_eol(_strip_headers(chunk))
        if payload.strip(b"\r\n"):               # ignore empty/whitespace parts
            out.append(payload)
    return out


def _sop_uid(blob: bytes) -> Optional[str]:
    """Best-effort SOPInstanceUID for naming; needs pydicom, else None."""
    try:
        import pydicom
        ds = pydicom.dcmread(io.BytesIO(blob), stop_before_pixels=True, force=True)
        uid = str(getattr(ds, "SOPInstanceUID", "")).strip()
        return uid or None
    except Exception:
        return None


def _instance_filename(blob: bytes, idx: int) -> str:
    uid = _sop_uid(blob)
    if uid and all(c.isdigit() or c == "." for c in uid):
        return f"{uid}.dcm"
    return f"instance_{idx:03d}.dcm"


def retrieve_study(client: DicomWebClient, study_uid: str, out_dir: str,
                   *, split: bool = True) -> list[str]:
    """Pull a whole study (multipart/related DICOM) and save it to *out_dir*.

    With ``split`` (default) the multipart body is parsed into individual
    ``.dcm`` instances — named by SOPInstanceUID when pydicom is available,
    else ``instance_NNN.dcm``. Returns the paths written. Falls back to saving
    the raw ``.multipart`` body when ``split`` is off or parsing yields nothing.
    """
    resp = client.get_raw(study_path(study_uid), accept=DICOM_MULTIPART_ACCEPT)
    resp.raise_for_status()
    os.makedirs(out_dir, exist_ok=True)

    if split:
        parts = split_multipart(resp.content, resp.headers.get("content-type", ""))
        if parts:
            written: list[str] = []
            for i, blob in enumerate(parts, 1):
                dest = os.path.join(out_dir, _instance_filename(blob, i))
                with open(dest, "wb") as fh:
                    fh.write(blob)
                written.append(dest)
            return written

    dest = os.path.join(out_dir, f"{study_uid}.multipart")
    with open(dest, "wb") as fh:
        fh.write(resp.content)
    return [dest]
