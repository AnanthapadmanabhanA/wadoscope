#!/usr/bin/env python3
"""Load sample DICOM studies into a wadoscope Orthanc lab.

Pulls small synthetic images bundled with pydicom (no network download) and
uploads them to Orthanc's /instances endpoint, then prints each
StudyInstanceUID and ready-to-run wadoscope commands.

    pip install pydicom httpx          # pydicom is only needed for this loader
    docker compose up -d               # start the lab(s) first

    # open lab (no auth):
    python load_samples.py
    # auth-enabled lab (port 8043, creds alice:alicepass):
    python load_samples.py --url http://localhost:8043 --basic alice:alicepass

    python load_samples.py --dry-run   # list sample UIDs without uploading
"""
from __future__ import annotations

import argparse
import json
import sys

# bundled with pydicom's package data (offline, no network fetch)
SAMPLES = ["CT_small.dcm", "MR_small.dcm", "rtplan.dcm"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed a wadoscope Orthanc lab with sample studies.")
    ap.add_argument("--url", default="http://localhost:8042", help="Orthanc base URL")
    ap.add_argument("--basic", metavar="USER:PASS", help="HTTP basic auth (for the auth lab)")
    ap.add_argument("--dry-run", action="store_true", help="don't upload; just show sample UIDs")
    ap.add_argument("--write-authz", metavar="FILE",
                    help="write a token->study map for authz_gateway.py (BOLA lab)")
    args = ap.parse_args()

    try:
        import pydicom
        from pydicom.data import get_testdata_file
    except ImportError:
        sys.exit("This loader needs pydicom:  pip install pydicom")

    httpx = None
    auth = None
    if not args.dry_run:
        try:
            import httpx  # noqa: F811
        except ImportError:
            sys.exit("Uploading needs httpx:  pip install httpx  (or use --dry-run)")
        if args.basic:
            if ":" not in args.basic:
                sys.exit("--basic must be in the form USER:PASS")
            u, p = args.basic.split(":", 1)
            auth = (u, p)
        try:
            info = httpx.get(f"{args.url}/system", auth=auth, timeout=10)
            info.raise_for_status()
            print(f"[ok] Orthanc reachable: {info.json().get('Name', '?')}")
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"[-] Cannot reach Orthanc at {args.url} ({exc}). "
                     f"Lab up?  cd docker && docker compose up -d   "
                     f"(auth lab needs --basic alice:alicepass)")

    loaded: list[tuple[str, str, str]] = []
    for name in SAMPLES:
        try:
            path = get_testdata_file(name)
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {name}: {exc}")
            continue
        if not path:
            print(f"[skip] {name}: not available")
            continue

        ds = pydicom.dcmread(path)
        study = str(getattr(ds, "StudyInstanceUID", ""))
        patient = str(getattr(ds, "PatientName", "(none)"))
        modality = str(getattr(ds, "Modality", "?"))

        if args.dry_run:
            print(f"[dry] {name:16} patient={patient!r} modality={modality}")
        else:
            with open(path, "rb") as fh:
                blob = fh.read()
            r = httpx.post(f"{args.url}/instances", content=blob, auth=auth,
                           headers={"Content-Type": "application/dicom"}, timeout=30)
            if r.status_code == 200:
                print(f"[ok] uploaded {name:16} patient={patient!r} modality={modality}")
            else:
                print(f"[warn] {name}: HTTP {r.status_code} {r.text[:120]}")
        loaded.append((patient, modality, study))

    if not loaded:
        sys.exit("No sample data available.")

    print("\nLoaded studies:")
    for patient, modality, study in loaded:
        print(f"  {modality:6} {patient:24} StudyInstanceUID={study}")

    if args.write_authz:
        tokens = {"alice-token": [loaded[0][2]],
                  "bob-token": [s for _, _, s in loaded[1:]]}
        with open(args.write_authz, "w") as fh:
            json.dump({"mode": "vulnerable", "tokens": tokens}, fh, indent=2)
        print(f"\n[ok] wrote authz map -> {args.write_authz}")
        print(f"      alice-token owns : {tokens['alice-token']}")
        print(f"      bob-token   owns : {tokens['bob-token']}")
        print( "      start the BOLA gateway (from docker/):")
        print( "        python authz_gateway.py --mode vulnerable   # BOLA present")
        print( "        python authz_gateway.py --mode secure       # BOLA fixed")

    base = args.url.rstrip("/") + "/dicom-web"
    first_study = loaded[0][2]
    cred = f" --basic {args.basic}" if args.basic else ""
    print("\nNow try wadoscope against this lab:")
    print(f"  python -m wadoscope discover {args.url}")
    print(f"  python -m wadoscope query    {base}{cred} --level studies")
    print(f"  python -m wadoscope retrieve {base}{cred} --study {first_study} --mode metadata")
    print(f"  python -m wadoscope bola     {base}{cred} --study {first_study}")
    print(f"  python -m wadoscope cors     {base}{cred}")


if __name__ == "__main__":
    main()
