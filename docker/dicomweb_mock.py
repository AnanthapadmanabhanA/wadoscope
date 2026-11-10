#!/usr/bin/env python3
"""A zero-dependency DICOMweb lab target for wadoscope — no Docker, no Orthanc.

Serves a small, intentionally-insecure DICOMweb surface (QIDO-RS, WADO-RS,
STOW-RS) under ``/dicom-web`` on localhost, seeded from the sample images that
ship with pydicom (no network download). It is the quickest way to exercise
wadoscope end-to-end, especially on Windows where Docker may not be installed.

    pip install pydicom          # the only dependency (already pulled in by ".[inject]")
    python dicomweb_mock.py      # serves http://127.0.0.1:8042/dicom-web

Then, in another terminal:

    python -m wadoscope discover http://127.0.0.1:8042
    python -m wadoscope query    http://127.0.0.1:8042/dicom-web --level studies
    python -m wadoscope xss      http://127.0.0.1:8042/dicom-web --unsafe

Flags:
    --reflect-cors   reflect any Origin + allow credentials, so `wadoscope cors`
                     reports a HIGH cross-origin-PHI finding (off by default).

Lab-only. Deliberately insecure (no auth, no object scoping). Never expose it.
"""
from __future__ import annotations

import argparse
import json
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pydicom
from pydicom.data import get_testdata_file

PREFIX = "/dicom-web"
SAMPLES = ["CT_small.dcm", "MR_small.dcm", "rtplan.dcm"]

# study_uid -> list of {"ds": Dataset, "raw": bytes}
STORE: dict[str, list[dict]] = {}
REFLECT_CORS = False

_RE_STUDY_META = re.compile(r"/studies/([^/]+)/metadata$")
_RE_SERIES_META = re.compile(r"/studies/([^/]+)/series/([^/]+)/metadata$")
_RE_INSTANCES = re.compile(r"/studies/([^/]+)/series/([^/]+)/instances$")
_RE_SERIES = re.compile(r"/studies/([^/]+)/series$")
_RE_STUDY = re.compile(r"/studies/([^/]+)$")


def _json_of(ds: pydicom.Dataset) -> dict:
    """DICOM+JSON for a dataset, minus bulk pixel data."""
    d = ds.copy()
    if "PixelData" in d:
        del d.PixelData
    return d.to_json_dict()


def _seed() -> None:
    for name in SAMPLES:
        path = get_testdata_file(name)
        if not path:
            continue
        with open(path, "rb") as fh:
            raw = fh.read()
        ds = pydicom.dcmread(path)
        STORE.setdefault(str(ds.StudyInstanceUID), []).append({"ds": ds, "raw": raw})


def _studies_json() -> list[dict]:
    out = []
    for insts in STORE.values():
        out.append(_json_of(insts[0]["ds"]))        # one representative per study
    return out


def _parse_stow(body: bytes, content_type: str) -> int:
    m = re.search(r"boundary=([^;]+)", content_type or "")
    if not m:
        return 0
    boundary = m.group(1).strip().strip('"')
    stored = 0
    for part in body.split(("--" + boundary).encode()):
        if b"application/dicom" not in part:
            continue
        hdr = part.find(b"\r\n\r\n")
        if hdr == -1:
            continue
        blob = part[hdr + 4:].rstrip(b"\r\n")
        try:
            ds = pydicom.dcmread(__import__("io").BytesIO(blob))
        except Exception:
            continue
        STORE.setdefault(str(ds.StudyInstanceUID), []).append({"ds": ds, "raw": blob})
        stored += 1
    return stored


class _Handler(BaseHTTPRequestHandler):
    server_version = "Orthanc/1.12.4"           # so `discover` fingerprints Orthanc
    sys_version = ""

    # ── helpers ──────────────────────────────────────────────────────────────
    def _cors(self) -> None:
        if REFLECT_CORS:
            origin = self.headers.get("Origin", "*")
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")

    def _send_json(self, status: int, obj) -> None:
        payload = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/dicom+json")
        self.send_header("Content-Length", str(len(payload)))
        self._cors()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _not_found(self) -> None:
        self._send_json(404, {"error": "not found"})

    # ── routing ──────────────────────────────────────────────────────────────
    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith(PREFIX):
            return self._not_found()
        sub = path[len(PREFIX):]
        if sub.rstrip("/").endswith("/studies") or sub.rstrip("/") == "/studies":
            n = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(n) if n else b""
            stored = _parse_stow(body, self.headers.get("Content-Type", ""))
            return self._send_json(200, {"status": "stored", "count": stored})
        return self._not_found()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith(PREFIX):
            return self._not_found()
        sub = path[len(PREFIX):]

        if (m := _RE_STUDY_META.search(sub)):
            insts = STORE.get(m.group(1))
            return self._send_json(200 if insts else 404,
                                   [_json_of(i["ds"]) for i in insts] if insts else {"error": "no such study"})
        if (m := _RE_SERIES_META.search(sub)):
            insts = STORE.get(m.group(1), [])
            sel = [i for i in insts if str(i["ds"].SeriesInstanceUID) == m.group(2)]
            return self._send_json(200, [_json_of(i["ds"]) for i in sel])
        if (m := _RE_INSTANCES.search(sub)):
            insts = STORE.get(m.group(1), [])
            sel = [i for i in insts if str(i["ds"].SeriesInstanceUID) == m.group(2)]
            return self._send_json(200, [_json_of(i["ds"]) for i in sel])
        if (m := _RE_SERIES.search(sub)):
            insts = STORE.get(m.group(1), [])
            return self._send_json(200, [_json_of(i["ds"]) for i in insts])
        if sub.rstrip("/").endswith("/studies"):
            return self._send_json(200, _studies_json())
        if (m := _RE_STUDY.search(sub)):
            insts = STORE.get(m.group(1))
            if not insts:
                return self._not_found()
            return self._send_multipart([i["raw"] for i in insts])
        return self._not_found()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send_multipart(self, blobs: list[bytes]) -> None:
        boundary = uuid.uuid4().hex
        crlf = b"\r\n"
        parts = []
        for blob in blobs:
            parts.append(b"--" + boundary.encode() + crlf
                         + b"Content-Type: application/dicom" + crlf + crlf
                         + blob + crlf)
        parts.append(b"--" + boundary.encode() + b"--" + crlf)
        body = b"".join(parts)
        self.send_response(200)
        self.send_header(
            "Content-Type",
            f'multipart/related; type="application/dicom"; boundary={boundary}')
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args) -> None:
        print("  mock <-", self.command, self.path[:90])


def main() -> None:
    global REFLECT_CORS
    ap = argparse.ArgumentParser(description="Zero-dependency DICOMweb lab target for wadoscope.")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8042)
    ap.add_argument("--reflect-cors", action="store_true",
                    help="reflect Origin + allow credentials (demo the cors HIGH finding)")
    args = ap.parse_args()
    REFLECT_CORS = args.reflect_cors

    _seed()
    base = f"http://{args.host}:{args.port}"
    print(f"dicomweb mock  {base}{PREFIX}   (seeded {len(STORE)} studies"
          f"{', CORS reflected' if REFLECT_CORS else ''})")
    for uid, insts in STORE.items():
        ds = insts[0]["ds"]
        print(f"  {getattr(ds, 'Modality', '?'):4} {str(getattr(ds, 'PatientName', '(none)')):22} {uid}")
    print("\nTry:")
    print(f"  python -m wadoscope discover {base}")
    print(f"  python -m wadoscope query    {base}{PREFIX} --level studies")
    print(f"  python -m wadoscope xss      {base}{PREFIX} --unsafe")
    if REFLECT_CORS:
        print(f"  python -m wadoscope cors     {base}{PREFIX}")
    print()
    try:
        ThreadingHTTPServer((args.host, args.port), _Handler).serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


if __name__ == "__main__":
    main()
