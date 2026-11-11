"""Discover DICOMweb endpoints and fingerprint the server / cloud service.

Probes common base paths, reports whether /studies answers, and — crucially —
whether it answers *without authentication*.  Also fingerprints well-known
servers and the cloud DICOM services (Google / Azure / AWS) from URL + headers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import httpx

COMMON_BASES = [
    "/dicom-web", "/dicomweb", "/wado-rs", "/qido-rs", "/rs", "/studies", "",
]

# host/header patterns -> product label
_CLOUD = [
    ("healthcare.googleapis.com", "Google Cloud Healthcare DICOM API"),
    ("dicom.azurehealthcareapis.com", "Azure Health Data Services (DICOM)"),
    ("dicom-medical-imaging", "AWS HealthImaging"),
    ("medical-imaging", "AWS HealthImaging"),
]
_SERVER_HINTS = [
    ("orthanc", "Orthanc"),
    ("dcm4chee", "dcm4chee-arc"),
    ("nginx", "nginx (reverse proxy)"),
    ("apache", "Apache (reverse proxy)"),
]


@dataclass
class Advisory:
    product: str
    summary: str
    url: str


# Curated, verified advisories for the DICOM servers we fingerprint. These are
# *known issues for the detected product*, not a confirmed finding — discover
# can't read the exact running version, so always verify it. Pointed at a live
# source; CVE IDs included only where verified.
CVE_NOTES: dict[str, Advisory] = {
    "orthanc": Advisory(
        "Orthanc",
        "CVE-2025-0896 — HTTP REST API reachable without authentication by "
        "default (CWE-306, CVSS 9.8); image-parser RCE/DoS bugs in older builds.",
        "https://nvd.nist.gov/vuln/detail/CVE-2025-0896",
    ),
    "dcm4che": Advisory(
        "dcm4chee-arc-light",
        "2025 advisories — unauthenticated study mass-deletion "
        "(GHSA-v4gf-mj3c-fhgw) and JPEG/MP4/multipart parser DoS; "
        "unauthenticated DICOM/HL7 access under review (CVEs pending).",
        "https://github.com/dcm4che/dcm4chee-arc-light/security/advisories",
    ),
}


@dataclass
class EndpointFinding:
    base_url: str
    reachable: bool = False
    status: Optional[int] = None
    auth_enforced: Optional[bool] = None       # None = unknown
    server: str = ""
    product: str = ""
    notes: list[str] = field(default_factory=list)


def _fingerprint(url: str, server_header: str) -> str:
    low = (url + " " + server_header).lower()
    for pat, label in _CLOUD:
        if pat in low:
            return label
    for pat, label in _SERVER_HINTS:
        if pat in low:
            return label
    return server_header or "unknown"


def advisory_for(product: str) -> Optional[Advisory]:
    """Return a known-CVE/advisory note for a fingerprinted product, or None."""
    low = (product or "").lower()
    for key, adv in CVE_NOTES.items():
        if key in low:
            return adv
    return None


def discover(root_url: str, verify_tls: bool = True,
             timeout: float = 15.0) -> list[EndpointFinding]:
    """Try each common base path under *root_url* and probe /studies."""
    root = root_url.rstrip("/")
    findings: list[EndpointFinding] = []
    with httpx.Client(verify=verify_tls, timeout=timeout,
                      follow_redirects=True) as c:
        for base in COMMON_BASES:
            base_url = root + base
            probe = base_url + "/studies"
            f = EndpointFinding(base_url=base_url)
            try:
                r = c.get(probe, params={"limit": "1"},
                          headers={"Accept": "application/dicom+json"})
            except httpx.HTTPError as exc:
                f.notes.append(f"error: {exc.__class__.__name__}")
                findings.append(f)
                continue

            f.reachable = True
            f.status = r.status_code
            f.server = r.headers.get("server", "")
            f.product = _fingerprint(base_url, f.server)

            if r.status_code in (401, 403):
                f.auth_enforced = True
            elif r.status_code in (200, 204):
                f.auth_enforced = False
                f.notes.append("UNAUTHENTICATED /studies responded — review access control")
            findings.append(f)
    return findings
