#!/usr/bin/env python3
"""A tiny DICOMweb authorization gateway for the wadoscope BOLA lab.

Vanilla Orthanc auth is all-or-nothing, so it can't demonstrate *per-object*
authorization. This gateway can. It sits in front of the open Orthanc and
enforces access by bearer token, in one of two modes:

  --mode secure      per-object authz enforced — a token may only read the
                     studies it owns (alice cannot read bob's study).
  --mode vulnerable  authenticated, but object ownership is NOT checked. This
                     is the BOLA bug: any valid token reaches any study by UID.

That gives `wadoscope bola` a real target — run it as alice against bob's
study and watch it get 403 (secure) vs 200 (vulnerable):

    # mapping is produced by:  python load_samples.py --write-authz authz.json
    python authz_gateway.py --orthanc http://localhost:8042 --port 8044 \
                            --authz authz.json --mode vulnerable
    python -m wadoscope bola http://localhost:8044/dicom-web \
                            --bearer alice-token --study <BOB_STUDY_UID>

Lab-only. This is a deliberately minimal proxy, not a hardened gateway.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

# matches a specific study object in the path: /studies/<uid>[/...]
# (any non-empty segment after /studies/ — a UID present means object access;
# bare /studies or /studies?... is a list/search endpoint)
_STUDY_RE = re.compile(r"/studies/([^/?]+)")

CFG: dict = {"mode": "vulnerable", "tokens": {}, "orthanc": "http://localhost:8042"}


def decide(token: str, path: str, cfg: dict) -> tuple[bool, int, str]:
    """Pure authorization decision. Returns (allow, status, reason)."""
    tokens = cfg["tokens"]
    if not token or token not in tokens:
        return (False, 401, "missing or invalid bearer token")

    m = _STUDY_RE.search(path)
    if not m:
        # list / search endpoints (e.g. /studies): any authenticated token
        return (True, 200, "authenticated (non-object endpoint)")

    study = m.group(1)
    if cfg["mode"] == "vulnerable":
        # BOLA: authentication is checked, object ownership is NOT
        return (True, 200, "vulnerable mode — object scope not enforced (BOLA)")

    if study in tokens[token]:
        return (True, 200, "owner match")
    return (False, 403, f"token not authorized for study {study}")


class _Handler(BaseHTTPRequestHandler):
    def _token(self) -> str:
        h = self.headers.get("Authorization", "")
        return h[7:].strip() if h.lower().startswith("bearer ") else ""

    def _handle(self) -> None:
        allow, status, reason = decide(self._token(), self.path, CFG)
        if not allow:
            self._json(status, {"error": reason})
            return
        # forward to the backing Orthanc
        url = CFG["orthanc"].rstrip("/") + self.path
        body = None
        if self.headers.get("Content-Length"):
            body = self.rfile.read(int(self.headers["Content-Length"]))
        try:
            up = httpx.request(
                self.command, url,
                headers={"Accept": self.headers.get("Accept", "application/dicom+json")},
                content=body, timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            self._json(502, {"error": f"backend unreachable: {exc}"})
            return
        self.send_response(up.status_code)
        self.send_header("Content-Type", up.headers.get("content-type", "application/json"))
        self.end_headers()
        self.wfile.write(up.content)

    def _json(self, status: int, obj: dict) -> None:
        payload = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _handle
    do_POST = _handle

    def log_message(self, *_a) -> None:   # keep stdout clean
        return


def main() -> None:
    ap = argparse.ArgumentParser(description="DICOMweb authorization gateway (wadoscope BOLA lab).")
    ap.add_argument("--orthanc", default="http://localhost:8042", help="backing Orthanc base URL")
    ap.add_argument("--port", type=int, default=8044)
    ap.add_argument("--authz", default="authz.json", help="token→study map (see load_samples.py --write-authz)")
    ap.add_argument("--mode", choices=["secure", "vulnerable"], default=None,
                    help="override the mode in the authz file")
    args = ap.parse_args()

    try:
        with open(args.authz) as fh:
            cfg = json.load(fh)
    except FileNotFoundError:
        sys.exit(f"authz file '{args.authz}' not found — run: "
                 f"python load_samples.py --write-authz {args.authz}")

    CFG["tokens"] = cfg.get("tokens", {})
    CFG["mode"] = args.mode or cfg.get("mode", "vulnerable")
    CFG["orthanc"] = args.orthanc

    print(f"authz gateway  :{args.port}  mode={CFG['mode']}  "
          f"orthanc={args.orthanc}  tokens={list(CFG['tokens'])}")
    ThreadingHTTPServer(("0.0.0.0", args.port), _Handler).serve_forever()


if __name__ == "__main__":
    main()
