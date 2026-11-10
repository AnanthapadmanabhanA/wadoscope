# wadoscope — contributor / agent context

A DICOMweb offensive toolkit (QIDO/WADO/STOW + web-layer checks). Python 3.10+,
built on `httpx`. DIMSE is intentionally out of scope — defer to dicomrecon/nmap.

## Layout
- `wadoscope/web/`     — DICOMweb client + QIDO/WADO/STOW + `inject` (`client.py` is the only httpx holder)
- `wadoscope/checks/`  — web-layer checks: `discover`, `cors`, `bola`, `ssrf`, `xss`
- `wadoscope/commands/`— one file per CLI subcommand; registered in `__main__.py`
- `wadoscope/target.py`— `parse_web_target(url, ...) -> WebTarget` (base URL + auth + TLS)
- `tests/`             — pytest; the pure builders/flatteners are unit-tested without a server

## Conventions (do not break)
- **Commands never import httpx directly** — go through `wadoscope.web.*` or `wadoscope.checks.*`.
- **All writes pass the safe-mode gate** in `DicomWebClient` (STOW is refused unless `--unsafe`).
- **CLI pattern:** print `BANNER` → argparse with named groups → `target_from_args` → run → `sys.exit`.
  Mirror `commands/query.py`.
- Keep URL/param builders pure functions so they stay unit-testable
  (`qido` builders, `ssrf.build_probes`/`match_hits`, `xss.scan_metadata_for_payload`).
- The `ssrf` callback listener is **stdlib http.server only** — it's a sink, not a
  DICOMweb client, so it must not pull in httpx.
- `xss` synthesises instances via `web/inject.py`, which imports **pydicom lazily**
  (optional dep). Catch `ImportError` in the command and tell the user to install it.

## Run
```bash
python -m wadoscope --help
python -m wadoscope <command> --help
pytest -q
```
