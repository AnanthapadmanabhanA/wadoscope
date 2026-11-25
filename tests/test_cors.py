"""Unit tests for the CORS check's severity classification (fake client, no server)."""
from __future__ import annotations

from wadoscope.checks.cors import PROBE_ORIGIN, check_cors


class _Resp:
    def __init__(self, headers):
        self.headers = headers
        self.status_code = 200


class _Client:
    """Minimal stand-in for DicomWebClient that returns preset CORS headers."""

    def __init__(self, headers):
        self._headers = headers

    def get_json(self, path, params=None, origin=None):
        return _Resp(self._headers)


def _run(headers, origin=PROBE_ORIGIN):
    return check_cors(_Client(headers), origin=origin)


def test_reflected_origin_with_credentials_is_high():
    f = _run({"access-control-allow-origin": PROBE_ORIGIN,
              "access-control-allow-credentials": "true"})
    assert f.origin_reflected and f.allow_credentials
    assert f.severity == "high"


def test_reflected_origin_without_credentials_is_medium():
    f = _run({"access-control-allow-origin": PROBE_ORIGIN})
    assert f.origin_reflected and not f.allow_credentials
    assert f.severity == "medium"


def test_wildcard_with_credentials_is_high():
    f = _run({"access-control-allow-origin": "*",
              "access-control-allow-credentials": "true"})
    assert f.wildcard and f.allow_credentials
    assert f.severity == "high"


def test_wildcard_without_credentials_is_low():
    f = _run({"access-control-allow-origin": "*"})
    assert f.wildcard and not f.allow_credentials
    assert f.severity == "low"


def test_no_acao_header_is_info():
    f = _run({})
    assert not f.wildcard and not f.origin_reflected
    assert f.severity == "info"


def test_credentials_value_is_case_insensitive():
    # "True" must still be read as credentialed
    f = _run({"access-control-allow-origin": PROBE_ORIGIN,
              "access-control-allow-credentials": "True"})
    assert f.allow_credentials and f.severity == "high"
