"""Safe read/validate/apply operations for the Composer configuration channel."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from app.core.project_config import DEFAULT_PROJECT_CONFIG, ProjectConfig, ProjectConfigError, load_project_config

_WRITE_LOCK = threading.Lock()


class RevisionConflict(RuntimeError):
    def __init__(self, current_revision: str) -> None:
        self.current_revision = current_revision
        super().__init__(f"revision conflict: current is {current_revision}")


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    config: ProjectConfig | None
    errors: list[str]


def _revision(config: ProjectConfig) -> str:
    payload = config.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def config_payload(config: ProjectConfig) -> dict[str, Any]:
    return config.model_dump(mode="json")


def read_current(path: str | Path | None = None) -> ProjectConfig:
    return load_project_config(path or DEFAULT_PROJECT_CONFIG)


def revision(config: ProjectConfig) -> str:
    return _revision(config)


def validate_candidate(raw: dict[str, Any], *, path: str | Path | None = None) -> ValidationResult:
    target = Path(path or DEFAULT_PROJECT_CONFIG)
    candidate_path = target.with_name(f".{target.stem}.validate.{uuid4().hex}.yaml")
    try:
        candidate_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
        candidate = load_project_config(candidate_path)
        return ValidationResult(True, candidate, [])
    except (ProjectConfigError, OSError, yaml.YAMLError, TypeError, ValueError) as exc:
        return ValidationResult(False, None, [str(exc)])
    finally:
        candidate_path.unlink(missing_ok=True)


def apply_candidate(raw: dict[str, Any], *, base_revision: str,
                    path: str | Path | None = None) -> ProjectConfig:
    target = Path(path or DEFAULT_PROJECT_CONFIG)
    with _WRITE_LOCK:
        current = load_project_config(target)
        current_revision = _revision(current)
        if current_revision != base_revision:
            raise RevisionConflict(current_revision)

        candidate_path = target.with_name(f".{target.stem}.validate.{uuid4().hex}.yaml")
        staged = target.with_name(f".{target.stem}.write.{uuid4().hex}.yaml")
        try:
            candidate_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
            candidate = load_project_config(candidate_path)
            backup = target.with_suffix(target.suffix + ".bak")
            backup.write_bytes(target.read_bytes())
            staged.write_bytes(candidate_path.read_bytes())
            os.replace(staged, target)
            return load_project_config(target)
        finally:
            candidate_path.unlink(missing_ok=True)
            staged.unlink(missing_ok=True)
