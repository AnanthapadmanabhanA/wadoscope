"""Web-layer security checks that only exist over DICOMweb (HTTP).

These are the differentiators vs. classic DIMSE tooling: unauthenticated
endpoint detection, CORS misconfiguration, and BOLA/IDOR on UIDs-in-URLs.
"""
