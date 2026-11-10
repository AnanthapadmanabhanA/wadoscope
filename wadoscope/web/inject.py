"""Synthesise small DICOM instances carrying attacker-controlled tag values.

Used by the stored-XSS check to STOW an instance whose free-text tags
(PatientName, StudyDescription, ...) contain a payload, then observe whether
the server returns it unsanitised over QIDO/WADO.

pydicom is an *optional* dependency (same as the lab loader) — it is imported
lazily so the core tool stays dependency-light.  Callers should catch
``ImportError`` and tell the user to ``pip install pydicom``.
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional

# Free-text tags that commonly flow into a web viewer's DOM.  keyword -> VR note.
# (PN tags serialise as {"Alphabetic": ...} in DICOM+JSON; the rest as strings.)
INJECTABLE_TAGS: dict[str, str] = {
    "PatientName": "PN",
    "ReferringPhysicianName": "PN",
    "StudyDescription": "LO",
    "SeriesDescription": "LO",
    "InstitutionName": "LO",
    "PatientComments": "LT",
}


def build_instance(tag_values: dict[str, str],
                   *, patient_id: str = "WADOSCOPE") -> tuple[bytes, str]:
    """Build a minimal valid Secondary-Capture DICOM instance whose tags are
    set from *tag_values* (keyword -> value).

    Returns ``(dicom_bytes, study_instance_uid)`` so the caller can retrieve the
    instance back by UID after storing it.  A tiny 2x2 8-bit image is included so
    real viewers will list and render it.  Fresh UIDs are generated per call.
    """
    import pydicom  # noqa: F401  (lazy optional dep)
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import (
        ExplicitVRLittleEndian,
        SecondaryCaptureImageStorage,
        generate_uid,
    )

    ds = Dataset()
    ds.SpecificCharacterSet = "ISO_IR 192"          # UTF-8, widest repertoire
    ds.PatientID = patient_id
    ds.PatientName = "WADOSCOPE^TEST"
    ds.Modality = "OT"
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SeriesNumber = 1
    ds.InstanceNumber = 1

    # attacker-controlled free-text tags
    for keyword, value in tag_values.items():
        setattr(ds, keyword, value)

    # minimal 2x2 greyscale image so the instance is a valid SC image
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows = 2
    ds.Columns = 2
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = bytes([0, 64, 128, 255])

    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = ds.SOPClassUID
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta = meta

    buf = BytesIO()
    try:                                            # pydicom >= 3.0
        ds.save_as(buf, little_endian=True, implicit_vr=False,
                   enforce_file_format=True)
    except TypeError:                               # pydicom 2.x
        ds.is_little_endian = True
        ds.is_implicit_VR = False
        ds.save_as(buf, write_like_original=False)
    return buf.getvalue(), str(ds.StudyInstanceUID)


def build_multipart(blobs: list[bytes]) -> tuple[bytes, str]:
    """Wrap raw DICOM blobs in a STOW-RS multipart/related body.

    Re-exported from web.stow so callers that already hold instance bytes don't
    have to round-trip through disk.
    """
    from .stow import _build_multipart
    return _build_multipart(blobs)
