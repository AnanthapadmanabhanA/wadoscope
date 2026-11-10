#!/usr/bin/env python3
"""SSRF demo sink for the wadoscope `ssrf` lab.

Mimics a DICOMweb retrieve/rendering backend that accepts a URL parameter and
dereferences it server-side — the real-world shape of SSRF-via-retrieve. Two
modes give a clean before/after:

  --mode vulnerable  fetches whatever URL the client supplies (SSRF present)
  --mode secure      only fetches allow-listed internal hosts (SSRF fixed)

Run it, then point wadoscope at it:

    python ssrf_lab.py --port 8045 --mode vulnerable
    python -m wadoscope ssrf http://127.0.0.1:8045/dicom-web --wait 4
    #   -> HIGH: SSRF confirmed via 'url' (out-of-band callback received)

    # flip to secure and the same probe no longer calls back:
    python ssrf_lab.py --port 8045 --mode secure

Lab-only. A deliberately minimal sink, not a real server.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

# the same candidate parameters wadoscope sprays
SINK_PARAMS = [
    "url", "uri", "location", "path", "src", "target",
    "dest", "callback", "webhook", "imageurl", "retrieveurl",
]

# in secure mode only these backends may be dereferenced (the attacker's
# callback host is never on this list, so the probe gets no call-back)
CFG: dict = {"mode": "vulnerable", "allowlist": ["pacs.internal", "pacs.internal:8042"]}


def decide_fetch(url: str, mode: str, allowlist: list[str]) -> tuple[bool, str]:
    """Pure policy: may the server dereference *url*?  Returns (allow, reason)."""
    if not url:
        return (False, "no sink parameter present")
    host = urlparse(url).netloc
    if mode == "vulnerable":
        return (True, f"vulnerable mode — dereferencing {host} unconditionally (SSRF)")
    if host in allowlist:
        return (True, f"allow-listed backend {host}")
    return (False, f"blocked host {host!r} — not an allow-listed backend")


class _Handler(BaseHTTPRequestHandler):
    def _handle(self) -> None:
        q = parse_qs(urlparse(self.path).query)
        sink = url = None
        for name in SINK_PARAMS:
            if name in q and q[name]:
                sink, url = name, q[name][0]
                break

        allow, reason = decide_fetch(url or "", CFG["mode"], CFG["allowlist"])
        fetched = False
        if allow and url:
            try:
                urlopen(url, timeout=3).read(64)        # the SSRF itself
                fetched = True
            except Exception as exc:                    # noqa: BLE001
                reason = f"{reason}; outbound fetch error: {exc}"

        body = json.dumps({
            "mode": CFG["mode"], "sink": sink, "url": url,
            "fetched": fetched, "detail": reason,
        }).encode()
        self.send_response(200 if allow else 403)
        self.send_header("Content-Type", "application/dicom+json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = _handle
    do_POST = _handle

    def log_message(self, fmt, *args) -> None:
        # one concise line per probe so you can watch the sink fire
        print("sink <-", self.path[:120])


def main() -> None:
    ap = argparse.ArgumentParser(description="SSRF demo sink (wadoscope ssrf lab).")
    ap.add_argument("--port", type=int, default=8045)
    ap.add_argument("--mode", choices=["secure", "vulnerable"], default="vulnerable")
    args = ap.parse_args()
    CFG["mode"] = args.mode
    print(f"ssrf sink :{args.port}  mode={CFG['mode']}  "
          f"allowlist={CFG['allowlist']}")
    ThreadingHTTPServer(("127.0.0.1", args.port), _Handler).serve_forever()


if __name__ == "__main__":
    main()
