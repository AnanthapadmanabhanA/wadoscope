"""DICOMweb client layer (QIDO-RS / WADO-RS / STOW-RS).

Commands must go through this package — never import httpx directly in a
command module (mirrors the clean separation the rest of the tool keeps).
"""
