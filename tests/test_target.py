import pytest

from wadoscope.target import parse_web_target


def test_defaults_to_https_and_strips_trailing_slash():
    t = parse_web_target("pacs.example.org:8042/dicom-web/")
    assert t.base_url == "https://pacs.example.org:8042/dicom-web"
    assert t.scheme == "https"
    assert t.auth == "none"
    assert t.verify_tls is True


def test_keeps_explicit_http():
    t = parse_web_target("http://10.0.0.5/dicomweb")
    assert t.base_url == "http://10.0.0.5/dicomweb"
    assert t.scheme == "http"


def test_basic_auth_detected():
    t = parse_web_target("https://h/dicom-web", username="u", password="p")
    assert t.auth == "basic" and t.username == "u" and t.password == "p"


def test_bearer_auth_detected():
    t = parse_web_target("https://h/dicom-web", token="abc")
    assert t.auth == "bearer" and t.token == "abc"


def test_empty_rejected():
    with pytest.raises(ValueError):
        parse_web_target("")
