"""Unit tests for discover's fingerprint → advisory mapping (pure, no network)."""
from __future__ import annotations

from wadoscope.checks.discover import _fingerprint, advisory_for


def test_fingerprint_orthanc_from_server_header():
    assert _fingerprint("http://h/dicom-web", "Orthanc/1.12.4") == "Orthanc"


def test_fingerprint_dcm4chee_from_server_header():
    assert _fingerprint("http://h/dcm4chee-arc", "") == "dcm4chee-arc"


def test_fingerprint_cloud_from_host():
    assert _fingerprint("https://x.healthcare.googleapis.com/v1", "") == \
        "Google Cloud Healthcare DICOM API"


def test_advisory_orthanc_cites_verified_cve():
    adv = advisory_for("Orthanc")
    assert adv is not None
    assert adv.product == "Orthanc"
    assert "CVE-2025-0896" in adv.summary
    assert adv.url.startswith("https://")


def test_advisory_dcm4chee_matches_label():
    adv = advisory_for("dcm4chee-arc")
    assert adv is not None
    assert "dcm4chee" in adv.product.lower()
    assert "GHSA-" in adv.summary


def test_advisory_none_for_unmapped_products():
    assert advisory_for("nginx (reverse proxy)") is None
    assert advisory_for("Google Cloud Healthcare DICOM API") is None
    assert advisory_for("") is None
    assert advisory_for("unknown") is None
