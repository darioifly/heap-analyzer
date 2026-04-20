"""Structured error classification for user-facing IPC errors.

Maps low-level exceptions from the I/O and processing layers to the
SPEC-defined error codes that the Electron parent process understands.
All messages are in Italian — the user-facing UI language.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorInfo:
    """Classified error ready to emit as JSON Lines."""

    code: str
    message: str


# Canonical SPEC error codes
CODE_CORRUPT_LAS = "CORRUPT_LAS"
CODE_MISSING_CRS = "MISSING_CRS"
CODE_CRS_MISMATCH = "CRS_MISMATCH"
CODE_HEAP_TOO_SMALL = "HEAP_TOO_SMALL"
CODE_HEAP_ANOMALOUS = "HEAP_ANOMALOUS"
CODE_NO_LIDAR_RETURNS = "NO_LIDAR_RETURNS"

# Area thresholds for heap-size edge cases
MIN_HEAP_AREA_M2 = 0.5


def classify_las_error(exc: BaseException) -> ErrorInfo:
    """Classify a LAS-loading exception into a CORRUPT_LAS / MISSING_CRS info.

    Args:
        exc: Raised exception from the LAS reader layer.

    Returns:
        ErrorInfo with a SPEC code and Italian message.
    """
    from heap_analyzer.io.las_reader import LasReaderError

    msg = str(exc).lower()
    if isinstance(exc, LasReaderError) or "too small" in msg or "magic" in msg:
        return ErrorInfo(CODE_CORRUPT_LAS, "File LAS non leggibile")
    if ("crs" in msg and "not" in msg) or "no crs" in msg:
        return ErrorInfo(
            CODE_MISSING_CRS,
            "Il file LAS non contiene un sistema di coordinate valido",
        )
    return ErrorInfo(CODE_CORRUPT_LAS, f"File LAS non leggibile: {exc}")


def classify_tiff_error(exc: BaseException) -> ErrorInfo:
    """Classify a TIFF-loading exception into a structured error.

    Args:
        exc: Raised exception from the GeoTIFF reader layer.

    Returns:
        ErrorInfo with a SPEC code and Italian message.
    """
    msg = str(exc).lower()
    if "crs" in msg:
        return ErrorInfo(
            CODE_MISSING_CRS,
            "Il file TIFF non contiene un sistema di coordinate valido",
        )
    return ErrorInfo(CODE_MISSING_CRS, f"File TIFF non valido: {exc}")


def is_heap_too_small(area_m2: float) -> bool:
    """Return True if a heap area is below the minimum-area safety floor."""
    return area_m2 < MIN_HEAP_AREA_M2


def is_heap_anomalous(heap_area_m2: float, survey_area_m2: float) -> bool:
    """Return True if a heap covers more than half the survey extent.

    That's never physically plausible for a steelworks site, so it flags a
    likely segmentation failure (one giant component instead of many heaps).
    """
    if survey_area_m2 <= 0:
        return False
    return heap_area_m2 > (survey_area_m2 / 2.0)
