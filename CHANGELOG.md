# Changelog

All notable changes to wadoscope are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims
to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

Nothing yet.

## [0.3.0] - 2026-11-20

### Added
- Zero-dependency DICOMweb mock lab (`docker/dicomweb_mock.py`) that serves a
  seeded QIDO/WADO/STOW surface from pydicom's sample data — a no-Docker
  quickstart, handy on Windows.
- `discover` maps a fingerprinted server to a known-CVE/advisory note: Orthanc
  (CVE-2025-0896, unauthenticated REST API by default) and dcm4chee-arc (2025
  GitHub advisories). Framed as a lead to verify against the running version,
  not a confirmed finding — `discover` can't read the exact version.
- `retrieve --mode study` splits the WADO-RS `multipart/related` response into
  per-instance `.dcm` files, named by SOPInstanceUID when pydicom is present.
  The split is byte-exact (instance bytes ending in `0x0A`/`0x0D` survive);
  `--no-split` keeps the raw multipart body.
- Animated, colour-cycled CLI banner (24-bit truecolour with a 256-colour
  fallback). Printed to stderr so stdout stays clean for piped output; honours
  `NO_COLOR`, `--no-banner` / `WADOSCOPE_NO_BANNER`, and non-interactive runs.
- Continuous integration: GitHub Actions runs the suite on Python 3.10–3.13;
  README gains tests / Python / license badges.
- End-to-end integration test that boots the mock lab in-process and drives
  `discover` and a QIDO query over real HTTP (suite: 38 tests).

### Changed
- `discover` now accepts `--no-banner`.
- README: banner image header, no-Docker quickstart section, updated command
  table and roadmap.

## [0.2.0] - 2026-11-10

### Added
- Initial release. A DICOMweb offensive toolkit focused on the HTTP layer;
  DIMSE is intentionally out of scope (defer to dicomrecon / nmap).
- Recon and transport: `discover`, `query` (QIDO-RS), `retrieve` (WADO-RS),
  `store` (STOW-RS).
- Web-layer checks: `cors` (cross-origin PHI exposure), `bola` (per-object
  authorization / IDOR on StudyInstanceUID), `ssrf` (out-of-band retrieve-sink
  probe), `xss` (stored XSS in DICOM metadata).
- Safe mode on by default: STOW-RS writes are refused unless `--unsafe`.
- Reproducible lab: Dockerised Orthanc (open and auth), a per-object BOLA
  authorization gateway, an SSRF sink, and a deliberately-vulnerable mini-viewer.
- pytest unit tests for the pure URL/param builders and parsers.
