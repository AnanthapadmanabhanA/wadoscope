# Draft tool abstract — Arsenal / Biohacking Village

*(Working draft for a tool-demo submission. Keep it honest: this is a tooling /
coverage contribution, not a new attack class.)*

---

**wadoscope: an offensive toolkit for DICOMweb and cloud medical imaging**

Hospital imaging runs on DICOM, and increasingly on **DICOMweb** — its HTTP/REST
profile (QIDO-RS, WADO-RS, STOW-RS). The modern cloud imaging services —
Google Cloud Healthcare, Azure DICOM service, AWS HealthImaging — are
DICOMweb-native. Yet the offensive tooling for medical imaging is still almost
entirely **DIMSE-only** (nmap's `dicom-*` scripts, dicomrecon, assorted
one-off scripts); none of it reaches the DICOMweb surface where imaging is
increasingly exposed, and where the interesting flaws are *web* flaws.

`wadoscope` fills that gap. It discovers and fingerprints DICOMweb endpoints
(including the cloud services), enumerates PHI over QIDO-RS, retrieves it over
WADO-RS, and — uniquely for a DICOM tool — runs the checks that only exist over
HTTP: **unauthenticated-endpoint detection, CORS misconfiguration (cross-origin
PHI theft), BOLA/IDOR on the StudyInstanceUID embedded in the URL path,
out-of-band SSRF probing of retrieve/URL sinks, and stored XSS injected through
DICOM metadata tags that web viewers render.** Every write passes a safe-mode
gate, and the tool ships with a Dockerized Orthanc lab — plus a per-object
authorization gateway, an SSRF sink, and a deliberately-vulnerable mini-viewer —
so each finding has a reproducible before/after without touching a real system.
It is the DICOMweb counterpart to the existing DIMSE tools, not a replacement
for them.

Attendees leave with a practical methodology and an open-source tool for
assessing the medical-imaging attack surface that cloud adoption is rapidly
expanding — and that current tooling ignores.

---

### Positioning notes (for the CFP form / Q&A)
- **What's new:** first dedicated DICOMweb *offensive* toolkit; the cloud-DICOM
  reach and the web-layer checks (unauth / CORS / BOLA / SSRF / stored-XSS) are
  the differentiators, each with a reproducible lab target.
- **What's not claimed:** no novel 0-day; the attack *classes* (SSRF, stored
  XSS, IDOR, CORS) are well known on the web — the contribution is bringing them
  to the DICOMweb surface in one tool, with consolidation, coverage, and a lab.
- **On the XSS/SSRF checks:** wadoscope proves the server-side half honestly —
  XSS = "tag stored and returned unescaped" (the viewer harness shows execution);
  SSRF = confirmed only on an out-of-band callback, never inferred from a response.
- **Prior art to cite up front:** dicomrecon & nmap `dicom-*` (DIMSE),
  IOActive's DICOM pentest work, the PE/DICOM polyglot (CVE-2019-11687).
- **Ethics:** authorized-use framing, safe-by-default, lab-only demos,
  coordinated disclosure for anything found in the wild.
