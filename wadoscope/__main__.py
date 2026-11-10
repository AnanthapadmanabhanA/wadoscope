"""
python -m wadoscope <command> [options]

A DICOMweb offensive toolkit. For classic DIMSE (C-FIND/C-STORE/C-MOVE) use
dicomrecon or nmap's dicom-* NSE scripts — this tool is the DICOMweb counterpart.
"""
from __future__ import annotations

import importlib
import sys

from wadoscope import banner

# command -> (module, one-line description)
_RECON: dict[str, tuple[str, str]] = {
    "discover": ("wadoscope.commands.discover",
                 "DISCOVER  — find DICOMweb endpoints, fingerprint, detect unauth access"),
    "query":    ("wadoscope.commands.query",
                 "QUERY     — QIDO-RS enumeration of studies/series/instances"),
    "retrieve": ("wadoscope.commands.retrieve",
                 "RETRIEVE  — WADO-RS metadata / study retrieval (exfiltration)"),
    "store":    ("wadoscope.commands.store",
                 "STORE     — STOW-RS injection (write; requires --unsafe)"),
}

_CHECKS: dict[str, tuple[str, str]] = {
    "cors": ("wadoscope.commands.cors",
             "CORS      — detect cross-origin PHI exposure"),
    "bola": ("wadoscope.commands.bola",
             "BOLA      — per-object authorization (IDOR on StudyInstanceUID)"),
    "ssrf": ("wadoscope.commands.ssrf",
             "SSRF      — out-of-band probe of retrieve/URL sinks"),
    "xss":  ("wadoscope.commands.xss",
             "XSS       — stored XSS in DICOM metadata (write; requires --unsafe)"),
}

_ALL = {**_RECON, **_CHECKS}


def _usage() -> None:
    banner.show()
    print("\nusage: python -m wadoscope <command> [options]\n", file=sys.stderr)
    print("dicomweb:", file=sys.stderr)
    for name, (_, desc) in _RECON.items():
        print(f"  {name:<10} {desc}", file=sys.stderr)
    print("\nweb-layer checks:", file=sys.stderr)
    for name, (_, desc) in _CHECKS.items():
        print(f"  {name:<10} {desc}", file=sys.stderr)
    print("\nRun 'python -m wadoscope <command> --help' for options.\n", file=sys.stderr)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        _usage()
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd not in _ALL:
        print(f"[-] Unknown command '{cmd}'", file=sys.stderr)
        print(f"    Available: {', '.join(_ALL)}", file=sys.stderr)
        sys.exit(1)

    module_path, _ = _ALL[cmd]
    sys.argv = [f"wadoscope {cmd}"] + sys.argv[2:]
    mod = importlib.import_module(module_path)
    mod.main()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
