from __future__ import annotations

from pathlib import Path

SOURCE_WORKBOOK = "Load Distribution.xlsx"
TIMING_REFERENCE_WORKBOOK = "TT Faculty_16_8_2026.xlsx"


def data_directory() -> Path:
    """Return the mounted data directory without assuming the process cwd.

    Docker mounts the repository data directory at ``/app/data``.  When the
    backend runs directly, the same files live in the repository's ``data``
    directory.  The old ``parents[3]`` calculation resolved to ``/`` inside
    Docker, which made a valid mounted workbook look missing.
    """
    candidates = (
        Path("/app/data"),
        Path(__file__).resolve().parents[3] / "data",
        Path.cwd() / "data",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def workbook_path(filename: str) -> Path:
    return data_directory() / "raw" / filename


def source_workbook_path() -> Path:
    return workbook_path(SOURCE_WORKBOOK)


def timing_reference_path() -> Path:
    return workbook_path(TIMING_REFERENCE_WORKBOOK)
