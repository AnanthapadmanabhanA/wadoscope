"""SSRF-via-retrieve check for DICOMweb (out-of-band).

Some DICOMweb deployments dereference a URL the client supplies: retrieve-by-
reference, image-rendering backends that proxy an external resource, and the
gateways/proxies that front cloud PACS.  Where that happens, a crafted retrieve
request coerces the server into fetching an attacker URL — SSRF reachable from
inside the hospital network.

Because the vulnerable parameter name varies by implementation, this check works
the way an SSRF scanner does: it sprays a set of candidate URL-parameters with a
unique **callback URL** and waits for the target to call back.  The out-of-band
hit — not the HTTP response — is the proof, and the per-parameter token tells us
which sink fired.  Everything here is read-only (GET), so it runs in safe mode.

`build_probes` and `match_hits` are pure and unit-tested; the callback listener
is stdlib-only (no httpx — that stays in the DICOMweb client).
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from ..web.client import DicomWebClient

# Candidate URL-parameter sink names seen across DICOMweb proxies, gateways and
# rendering backends.  The out-of-band callback is the source of truth; these
# are simply the parameters we spray with the callback URL.
SINK_PARAMS = [
    "url", "uri", "location", "path", "src", "target",
    "dest", "callback", "webhook", "imageurl", "retrieveurl",
]

# Retrieve endpoints to attach the sink parameters to.
PROBE_PATHS = ["/studies"]


@dataclass
class ProbeSpec:
    sink: str                       # the parameter name under test
    path: str                       # endpoint it was attached to
    params: dict[str, str]          # query params actually sent
    token: str                      # unique marker expected in the callback


def build_probes(callback_base: str, token: str,
                 *, paths: Optional[list[str]] = None,
                 params: Optional[list[str]] = None) -> list[ProbeSpec]:
    """Pure builder: one probe per (path, sink-parameter), each carrying a unique
    callback URL of the form ``<callback_base>/<token>-<param>``.
    """
    paths = paths or list(PROBE_PATHS)
    params = params or list(SINK_PARAMS)
    base = callback_base.rstrip("/")
    probes: list[ProbeSpec] = []
    for path in paths:
        for pname in params:
            marker = f"{token}-{pname}"
            probes.append(ProbeSpec(
                sink=pname, path=path,
                params={pname: f"{base}/{marker}"}, token=marker,
            ))
    return probes


def match_hits(hit_paths: list[str], probes: list[ProbeSpec]) -> list[str]:
    """Pure: given the request paths seen by the callback listener, return the
    sink parameter names whose unique token appeared in a hit.
    """
    confirmed: set[str] = set()
    for pr in probes:
        if any(pr.token in hp for hp in hit_paths):
            confirmed.add(pr.sink)
    return sorted(confirmed)


# ── out-of-band callback listener (stdlib only) ────────────────────────────────

class _CBHandler(BaseHTTPRequestHandler):
    def _record(self) -> None:
        self.server.hits.append(self.path)            # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    do_GET = _record
    do_POST = _record

    def log_message(self, *_a) -> None:               # keep stdout clean
        return


class CallbackServer:
    """A tiny HTTP sink that records the paths it is called on."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self._srv = ThreadingHTTPServer((host, port), _CBHandler)
        self._srv.hits = []                           # type: ignore[attr-defined]
        self.host, self.port = self._srv.server_address[0], self._srv.server_address[1]
        self._thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def hits(self) -> list[str]:
        return list(self._srv.hits)                   # type: ignore[attr-defined]

    def start(self) -> "CallbackServer":
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._srv.shutdown()
        self._srv.server_close()


# ── orchestration ──────────────────────────────────────────────────────────────

@dataclass
class SsrfFinding:
    sink: str
    confirmed: bool = True
    severity: str = "high"
    detail: str = ""


@dataclass
class SsrfResult:
    token: str = ""
    callback_base: str = ""
    probes_sent: int = 0
    listener_used: bool = False
    findings: list[SsrfFinding] = field(default_factory=list)

    @property
    def confirmed(self) -> bool:
        return bool(self.findings)


def check_ssrf(client: DicomWebClient,
               *, listener: Optional[CallbackServer] = None,
               callback_base: Optional[str] = None,
               paths: Optional[list[str]] = None,
               params: Optional[list[str]] = None,
               token: Optional[str] = None,
               wait: float = 4.0) -> SsrfResult:
    """Spray candidate SSRF sinks with a callback URL and report confirmed hits.

    Provide *listener* (a started :class:`CallbackServer`) for auto-confirmation,
    or *callback_base* alone to point at an external collaborator you watch
    yourself.  All probes are GET requests — read-only — so this never writes.
    """
    if callback_base is None:
        if listener is None:
            raise ValueError("check_ssrf needs a listener or a callback_base")
        callback_base = listener.base_url

    token = token or uuid.uuid4().hex[:12]
    probes = build_probes(callback_base, token, paths=paths, params=params)

    sent = 0
    for pr in probes:
        try:
            client.get_json(pr.path, params=pr.params)
            sent += 1
        except Exception:       # noqa: BLE001 — a dead sink / timeout is just a non-hit
            pass

    findings: list[SsrfFinding] = []
    if listener is not None:
        time.sleep(wait)
        for sink in match_hits(listener.hits(), probes):
            findings.append(SsrfFinding(
                sink=sink,
                detail=f"target fetched the attacker URL supplied in the "
                       f"'{sink}' parameter (out-of-band callback received)",
            ))

    return SsrfResult(token=token, callback_base=callback_base, probes_sent=sent,
                      listener_used=listener is not None, findings=findings)
