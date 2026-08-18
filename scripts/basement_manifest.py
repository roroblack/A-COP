"""Declarative definition of the files that make up the basement export."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

# Keep this list explicit: changing the basement boundary is a deliberate
# versioning decision, not an accidental consequence of directory crawling.
BASEMENT_COMPONENTS: tuple[str, ...] = (
    "app/core",
    "app/domain",
    "app/application",
    "app/infrastructure",
    "app/presentation",
)
EXCLUDED_PATTERNS: tuple[str, ...] = ("__pycache__", "*.pyc")

# This migration belongs to the sample domain rather than the reusable
# basement.  It is kept separate from the generic patterns so the boundary
# remains easy to review when the sample gains more migrations.
EXCLUDED_FILES: tuple[str, ...] = (
    "app/infrastructure/db/migrations/002_domain_*.sql",
)

BASEMENT_VERSION = "0.2.0"
CONTRACT_VERSION = "1.0"
EXPORT_TOOL_VERSION = "1"


def _matches_exclusion(relative_path: str, path: Path) -> bool:
    """Return whether a repository-relative path is outside the export."""

    if any(part in EXCLUDED_PATTERNS for part in path.parts):
        return True
    if any(fnmatch(relative_path, pattern) for pattern in EXCLUDED_FILES):
        return True
    return path.suffix == ".pyc"


def basement_files(root: Path | str) -> list[Path]:
    """Return existing basement files in stable, repository-relative order."""

    root = Path(root).resolve()
    files: list[Path] = []
    for component in BASEMENT_COMPONENTS:
        component_root = root / component
        if not component_root.exists():
            continue
        for path in component_root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if not _matches_exclusion(relative, path):
                files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def excluded_entries() -> list[str]:
    """Return the declared exclusions for inclusion in the artifact."""

    return [*EXCLUDED_PATTERNS, *EXCLUDED_FILES]
