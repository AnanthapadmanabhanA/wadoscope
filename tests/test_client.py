import pytest

from wadoscope.target import parse_web_target
from wadoscope.web.client import DicomWebClient, SafeModeError


def _target():
    return parse_web_target("https://pacs.example.org/dicom-web")


def test_safe_mode_blocks_stow():
    with DicomWebClient(_target(), safe_mode=True) as c:
        with pytest.raises(SafeModeError):
            c.post_multipart("/studies", b"x", "multipart/related")


def test_unsafe_allows_attempt(monkeypatch):
    # with safe_mode off, _guard_write must NOT raise (we stop before real I/O)
    c = DicomWebClient(_target(), safe_mode=False)
    try:
        c._guard_write("STOW-RS store")   # should not raise
    finally:
        c.close()


def test_bearer_header_set():
    t = parse_web_target("https://h/dicom-web", token="tok123")
    with DicomWebClient(t) as c:
        assert c._c.headers.get("Authorization") == "Bearer tok123"
