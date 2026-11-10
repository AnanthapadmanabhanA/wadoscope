"""Unit tests for the stored-XSS metadata scanner (pure functions, no server)."""
from __future__ import annotations

import pytest

from wadoscope.checks.xss import (
    DEFAULT_PAYLOAD,
    _html_escape,
    scan_metadata_for_payload,
)


def _meta(patient_name_value):
    """One DICOM+JSON object with PatientName set to the given raw string."""
    return [{"00100010": {"vr": "PN", "Value": [{"Alphabetic": patient_name_value}]}}]


def test_verbatim_payload_is_high_and_unescaped():
    meta = _meta(DEFAULT_PAYLOAD)
    findings = scan_metadata_for_payload(meta, DEFAULT_PAYLOAD, ["PatientName"])
    assert len(findings) == 1
    f = findings[0]
    assert f.tag == "PatientName"
    assert f.stored and f.unescaped
    assert f.severity == "high"


def test_html_encoded_payload_is_stored_but_safe():
    meta = _meta(_html_escape(DEFAULT_PAYLOAD))
    findings = scan_metadata_for_payload(meta, DEFAULT_PAYLOAD, ["PatientName"])
    assert len(findings) == 1
    f = findings[0]
    assert f.stored and not f.unescaped
    assert f.severity == "info"


def test_stripped_payload_is_not_stored():
    meta = _meta("WADOSCOPE^TEST")          # server dropped the payload
    findings = scan_metadata_for_payload(meta, DEFAULT_PAYLOAD, ["PatientName"])
    assert len(findings) == 1
    assert not findings[0].stored


def test_absent_tag_yields_no_finding():
    meta = [{"00080060": {"vr": "CS", "Value": ["OT"]}}]  # no PatientName
    findings = scan_metadata_for_payload(meta, DEFAULT_PAYLOAD, ["PatientName"])
    assert findings == []


def test_string_vr_payload_detected():
    payload = "<svg onload=alert(1)>"
    meta = [{"00081030": {"vr": "LO", "Value": [payload]}}]  # StudyDescription
    findings = scan_metadata_for_payload(meta, payload, ["StudyDescription"])
    assert findings and findings[0].unescaped


def test_build_instance_roundtrips_payload():
    pydicom = pytest.importorskip("pydicom")
    from io import BytesIO
    from wadoscope.web.inject import build_instance

    blob, study_uid = build_instance({"PatientName": DEFAULT_PAYLOAD})
    assert study_uid
    ds = pydicom.dcmread(BytesIO(blob))
    assert DEFAULT_PAYLOAD in str(ds.PatientName)
    assert str(ds.StudyInstanceUID) == study_uid
