"""Thin httpx wrapper for DICOMweb, with a central safe-mode gate.

All HTTP goes through here so that:
  * auth (basic / bearer) and TLS-verify are configured in one place, and
  * every state-changing request (STOW-RS store) passes the safe-mode check.
"""
from __future__ import annotations

from typing import Optional

import httpx

from ..target import WebTarget

# DICOMweb media types
JSON_ACCEPT = "application/dicom+json"
DICOM_MULTIPART_ACCEPT = 'multipart/related; type="application/dicom"'


class SafeModeError(RuntimeError):
    """Raised when a write (STOW/DELETE) is attempted while safe mode is on."""


class DicomWebClient:
    """Wraps an httpx.Client bound to a WebTarget."""

    def __init__(self, target: WebTarget, safe_mode: bool = True):
        self.target = target
        self.safe_mode = safe_mode

        headers: dict[str, str] = {}
        auth: Optional[tuple[str, str]] = None
        if target.auth == "bearer" and target.token:
            headers["Authorization"] = f"Bearer {target.token}"
        elif target.auth == "basic" and target.username:
            auth = (target.username, target.password)

        self._c = httpx.Client(
            base_url=target.base_url,
            headers=headers,
            auth=auth,
            verify=target.verify_tls,
            timeout=target.timeout,
            follow_redirects=True,
        )

    # ── reads ────────────────────────────────────────────────────────────────
    def get_json(self, path: str, params: Optional[dict] = None,
                 origin: Optional[str] = None) -> httpx.Response:
        headers = {"Accept": JSON_ACCEPT}
        if origin:
            headers["Origin"] = origin
        return self._c.get(path, params=params or {}, headers=headers)

    def get_raw(self, path: str, accept: Optional[str] = None,
                origin: Optional[str] = None) -> httpx.Response:
        headers: dict[str, str] = {}
        if accept:
            headers["Accept"] = accept
        if origin:
            headers["Origin"] = origin
        return self._c.get(path, headers=headers)

    def options(self, path: str, origin: Optional[str] = None,
                request_method: str = "GET") -> httpx.Response:
        headers: dict[str, str] = {}
        if origin:
            headers["Origin"] = origin
            headers["Access-Control-Request-Method"] = request_method
        return self._c.request("OPTIONS", path, headers=headers)

    # ── writes (guarded) ──────────────────────────────────────────────────────
    def post_multipart(self, path: str, body: bytes, content_type: str) -> httpx.Response:
        self._guard_write("STOW-RS store")
        return self._c.post(
            path,
            content=body,
            headers={"Content-Type": content_type, "Accept": JSON_ACCEPT},
        )

    def _guard_write(self, what: str) -> None:
        if self.safe_mode:
            raise SafeModeError(
                f"{what} blocked: safe mode is ON. Re-run with --unsafe to allow "
                f"writes (only against systems you are authorised to test)."
            )

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def close(self) -> None:
        self._c.close()

    def __enter__(self) -> "DicomWebClient":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
