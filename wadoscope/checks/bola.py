"""BOLA / IDOR check on DICOMweb object UIDs.

DICOMweb puts the StudyInstanceUID directly in the URL path
(``/studies/{uid}/metadata``).  If authorization is enforced per-endpoint
rather than per-object, a user (or an unauthenticated client) can reach studies
that belong to someone else simply by knowing/guessing the UID.

This check retrieves a target study's metadata through the *current* client
(which may be unauthenticated, or authenticated as a low-privilege user) and
reports whether access succeeded.  Supply a UID that the current principal
should NOT be able to see to make it a true BOLA test.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..web.client import DicomWebClient
from ..web import wado


@dataclass
class BolaFinding:
    study_uid: str
    accessible: bool = False
    status: int = 0
    severity: str = "info"
    detail: str = ""


def check_bola(client: DicomWebClient, study_uid: str) -> BolaFinding:
    f = BolaFinding(study_uid=study_uid)
    resp = client.get_json(wado.study_metadata_path(study_uid))
    f.status = resp.status_code
    if resp.status_code in (200, 204):
        f.accessible = True
        f.severity = "high"
        f.detail = (
            "Study metadata retrieved for a UID the current principal "
            "should not access — per-object authorization appears missing "
            "(BOLA/IDOR)."
        )
    elif resp.status_code in (401, 403):
        f.detail = "Access denied (authorization enforced for this UID)."
    elif resp.status_code == 404:
        f.detail = "Not found (UID absent, or hidden from this principal)."
    else:
        f.detail = f"Unexpected status {resp.status_code}."
    return f
