"""Parse a DICOMweb target: a base URL plus optional auth and TLS settings.

Unlike classic DIMSE (``[AET@]host:port``), DICOMweb is addressed by an HTTP(S)
base URL, e.g.::

    https://pacs.example.org:8042/dicom-web
    http://10.0.0.5/dicomweb

The calling code supplies credentials separately (``--basic`` / ``--bearer``).
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class WebTarget:
    base_url:   str
    auth:       str = "none"      # "none" | "basic" | "bearer"
    username:   str = ""
    password:   str = ""
    token:      str = ""
    verify_tls: bool = True
    timeout:    float = 30.0

    @property
    def scheme(self) -> str:
        return urlparse(self.base_url).scheme

    def __str__(self) -> str:
        return f"{self.base_url}  (auth={self.auth}, tls_verify={self.verify_tls})"


def parse_web_target(
    url: str,
    *,
    username: str = "",
    password: str = "",
    token: str = "",
    verify_tls: bool = True,
    timeout: float = 30.0,
) -> WebTarget:
    """Normalise *url* into a WebTarget. Raises ValueError on bad input."""
    u = (url or "").strip()
    if not u:
        raise ValueError("Empty target URL")
    if not u.startswith(("http://", "https://")):
        u = "https://" + u                      # default to TLS

    parsed = urlparse(u)
    if not parsed.netloc:
        raise ValueError(f"Cannot parse target URL '{url}'")

    base = u.rstrip("/")

    if token:
        auth = "bearer"
    elif username:
        auth = "basic"
    else:
        auth = "none"

    return WebTarget(
        base_url=base,
        auth=auth,
        username=username,
        password=password,
        token=token,
        verify_tls=verify_tls,
        timeout=timeout,
    )
