"""Unit tests for the BOLA check's status classification (fake client, no server)."""
from __future__ import annotations

from wadoscope.checks.bola import check_bola


class _Resp:
    def __init__(self, status_code):
        self.status_code = status_code
        self.headers = {}


class _Client:
    """Minimal stand-in for DicomWebClient that returns a preset status."""

    def __init__(self, status_code):
        self._status = status_code

    def get_json(self, path, params=None, origin=None):
        return _Resp(self._status)


def _run(status):
    return check_bola(_Client(status), "1.2.3.EXAMPLE.STUDY")


def test_200_is_high_and_accessible():
    f = _run(200)
    assert f.accessible and f.status == 200 and f.severity == "high"


def test_204_is_high_and_accessible():
    f = _run(204)
    assert f.accessible and f.severity == "high"


def test_403_is_denied_and_info():
    f = _run(403)
    assert not f.accessible and f.severity == "info"
    assert "denied" in f.detail.lower()


def test_401_is_denied():
    f = _run(401)
    assert not f.accessible and f.severity == "info"


def test_404_is_not_found():
    f = _run(404)
    assert not f.accessible and "not found" in f.detail.lower()


def test_unexpected_status_is_reported():
    f = _run(500)
    assert not f.accessible and "500" in f.detail
