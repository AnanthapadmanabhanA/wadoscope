"""CORS misconfiguration check for DICOMweb endpoints.

DICOMweb is consumed by browser-based viewers, so a permissive CORS policy can
let an attacker's web page read PHI cross-origin.  We send a probe Origin and
inspect the Access-Control-Allow-* response headers.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..web.client import DicomWebClient

PROBE_ORIGIN = "https://evil.example"


@dataclass
class CorsFinding:
    origin_reflected: bool = False
    wildcard: bool = False
    allow_credentials: bool = False
    acao: str = ""
    severity: str = "info"
    detail: str = ""


def check_cors(client: DicomWebClient, origin: str = PROBE_ORIGIN) -> CorsFinding:
    # a GET with Origin is enough to observe the server's ACAO handling
    resp = client.get_json("/studies", params={"limit": "1"}, origin=origin)
    acao = resp.headers.get("access-control-allow-origin", "")
    acac = resp.headers.get("access-control-allow-credentials", "").lower() == "true"

    f = CorsFinding(acao=acao, allow_credentials=acac)
    f.wildcard = acao == "*"
    f.origin_reflected = acao == origin

    if f.origin_reflected and f.allow_credentials:
        f.severity = "high"
        f.detail = ("Reflects arbitrary Origin AND allows credentials — a "
                    "malicious site can read authenticated PHI cross-origin.")
    elif f.origin_reflected:
        f.severity = "medium"
        f.detail = "Reflects arbitrary Origin (no credentials) — review CORS policy."
    elif f.wildcard and f.allow_credentials:
        f.severity = "high"
        f.detail = "Wildcard ACAO with credentials (browser-blocked, but misconfigured)."
    elif f.wildcard:
        f.severity = "low"
        f.detail = "Wildcard ACAO — any origin may read responses."
    else:
        f.severity = "info"
        f.detail = f"ACAO={acao!r} — no obvious cross-origin exposure."
    return f
