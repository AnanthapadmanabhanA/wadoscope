"""STOW-RS — store instances over HTTP (injection primitive).

Writes are gated by the client's safe-mode (see DicomWebClient.post_multipart):
nothing is sent unless the caller explicitly ran with --unsafe.
"""
from __future__ import annotations

import os
import uuid
from typing import Iterable

from .client import DicomWebClient


def _build_multipart(dicom_blobs: list[bytes]) -> tuple[bytes, str]:
    """Assemble a multipart/related body of application/dicom parts."""
    boundary = uuid.uuid4().hex
    crlf = b"\r\n"
    parts: list[bytes] = []
    for blob in dicom_blobs:
        parts.append(
            b"--" + boundary.encode() + crlf
            + b"Content-Type: application/dicom" + crlf + crlf
            + blob + crlf
        )
    parts.append(b"--" + boundary.encode() + b"--" + crlf)
    body = b"".join(parts)
    content_type = (
        f'multipart/related; type="application/dicom"; boundary={boundary}'
    )
    return body, content_type


def _read_files(paths: Iterable[str]) -> list[bytes]:
    blobs: list[bytes] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _d, files in os.walk(p):
                for f in files:
                    with open(os.path.join(root, f), "rb") as fh:
                        blobs.append(fh.read())
        else:
            with open(p, "rb") as fh:
                blobs.append(fh.read())
    return blobs


def stow_store(client: DicomWebClient, paths: Iterable[str]):
    """POST DICOM files to /studies via STOW-RS. Honours safe mode."""
    blobs = _read_files(paths)
    if not blobs:
        raise ValueError("No DICOM files found to store")
    body, content_type = _build_multipart(blobs)
    return client.post_multipart("/studies", body, content_type)
