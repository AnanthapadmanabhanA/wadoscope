"""Unit tests for the SSRF prober's pure builders and the callback listener."""
from __future__ import annotations

from urllib.request import urlopen

from wadoscope.checks.ssrf import (
    CallbackServer,
    build_probes,
    match_hits,
)


def test_build_probes_cardinality_and_shape():
    probes = build_probes("http://cb.example", "tok",
                          paths=["/studies"], params=["url", "uri"])
    assert len(probes) == 2
    by_sink = {p.sink: p for p in probes}
    assert set(by_sink) == {"url", "uri"}
    # each probe carries its own param with a unique marker URL
    assert by_sink["url"].params == {"url": "http://cb.example/tok-url"}
    assert by_sink["uri"].token == "tok-uri"


def test_build_probes_multiplies_paths_by_params():
    probes = build_probes("http://cb", "t",
                          paths=["/studies", "/series"], params=["url", "src", "dest"])
    assert len(probes) == 6


def test_match_hits_identifies_the_firing_sink():
    probes = build_probes("http://cb", "tok", paths=["/studies"],
                          params=["url", "uri", "dest"])
    # the target only called back on the 'uri' marker
    hits = ["/tok-uri", "/favicon.ico"]
    assert match_hits(hits, probes) == ["uri"]


def test_match_hits_empty_when_no_callback():
    probes = build_probes("http://cb", "tok", paths=["/studies"], params=["url"])
    assert match_hits([], probes) == []
    assert match_hits(["/unrelated"], probes) == []


def test_callback_server_records_hits():
    srv = CallbackServer("127.0.0.1", 0).start()
    try:
        urlopen(f"{srv.base_url}/tok-url", timeout=3).read()
        assert any("/tok-url" in h for h in srv.hits())
    finally:
        srv.stop()
