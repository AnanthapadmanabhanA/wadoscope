"""End-to-end integration test: the no-Docker mock lab against the live client path.

The other test modules cover pure builders/parsers. This one boots
``docker/dicomweb_mock.py`` in-process on an ephemeral port and drives the real
HTTP paths — discover's base-path probe and a QIDO-RS query through the httpx
client — so the lab target and the client layer are exercised in CI, not just
the pure functions.
"""
from __future__ import annotations

import importlib.util
import pathlib
import threading
from http.server import ThreadingHTTPServer

import pytest

pytest.importorskip("pydicom")   # the mock seeds from pydicom's bundled samples

from wadoscope.checks.discover import advisory_for, discover
from wadoscope.target import parse_web_target
from wadoscope.web import qido
from wadoscope.web.client import DicomWebClient


def _load_mock():
    path = pathlib.Path(__file__).resolve().parent.parent / "docker" / "dicomweb_mock.py"
    spec = importlib.util.spec_from_file_location("dicomweb_mock_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mock_base():
    mock = _load_mock()
    mock._seed()
    assert mock.STORE, "mock seeded no studies (pydicom sample data missing?)"
    mock._Handler.log_message = lambda *a, **k: None   # keep test output quiet

    srv = ThreadingHTTPServer(("127.0.0.1", 0), mock._Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        srv.shutdown()
        srv.server_close()


def test_discover_flags_unauthenticated_dicomweb(mock_base):
    findings = discover(mock_base, timeout=5.0)
    dw = [f for f in findings if f.base_url.endswith("/dicom-web")]
    assert dw, "discover never probed the /dicom-web base"
    f = dw[0]
    assert f.reachable and f.status == 200
    assert f.auth_enforced is False                       # unauth /studies answered
    assert f.product == "Orthanc"                         # fingerprinted from Server header
    assert any("UNAUTHENTICATED" in n for n in f.notes)


def test_discover_attaches_known_advisory(mock_base):
    findings = discover(mock_base, timeout=5.0)
    assert "Orthanc" in {f.product for f in findings if f.reachable}
    adv = advisory_for("Orthanc")
    assert adv is not None and "CVE-2025-0896" in adv.summary


def test_qido_query_returns_seeded_studies(mock_base):
    target = parse_web_target(mock_base + "/dicom-web")
    with DicomWebClient(target) as client:
        studies = qido.search_studies(client, limit=50)
    assert studies, "QIDO query returned no studies"
    assert any(s.get("PatientName") for s in studies)     # PHI exposed over the wire
    assert all(s.get("StudyInstanceUID") for s in studies)
