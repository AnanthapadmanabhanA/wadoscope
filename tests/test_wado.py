"""Unit tests for WADO-RS multipart splitting (pure, no network)."""
from __future__ import annotations

from wadoscope.web.stow import _build_multipart
from wadoscope.web.wado import _boundary, _instance_filename, split_multipart


def test_boundary_plain_and_quoted():
    assert _boundary('multipart/related; type="application/dicom"; boundary=abc123') == "abc123"
    assert _boundary('multipart/related; boundary="xy-z_1"') == "xy-z_1"
    assert _boundary("application/dicom") is None


def test_split_roundtrips_the_builder():
    blobs = [b"\x00" * 128 + b"DICMfirst-instance", b"second-\xff\x00-blob"]
    body, ctype = _build_multipart(blobs)
    assert split_multipart(body, ctype) == blobs


def test_split_preserves_trailing_newline_bytes():
    # instances whose bytes legitimately end in 0x0A / 0x0D must survive intact
    blobs = [b"ends-with-lf\n", b"ends-with-crlf\r\n", b"normal"]
    body, ctype = _build_multipart(blobs)
    assert split_multipart(body, ctype) == blobs


def test_split_single_instance():
    blob = b"\x00" * 128 + b"DICMonly"
    body, ctype = _build_multipart([blob])
    out = split_multipart(body, ctype)
    assert out == [blob]


def test_split_without_boundary_is_empty():
    assert split_multipart(b"not multipart at all", "application/dicom") == []


def test_instance_filename_falls_back_to_index_without_uid():
    # a non-DICOM blob has no SOPInstanceUID -> indexed name
    assert _instance_filename(b"not a dicom file", 3) == "instance_003.dcm"
