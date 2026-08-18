from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from scripts.basement_manifest import BASEMENT_COMPONENTS, basement_files
from scripts.export_basement import export_basement


def _write(root, relative: str, content: str = "x"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_manifest_matches_declared_files_and_hashes(tmp_path):
    _write(tmp_path, "app/core/contracts.py", "contract")
    _write(tmp_path, "app/domain/model.py", "domain")
    _write(tmp_path, "app/infrastructure/db/migrations/001_schema.sql", "schema")
    _write(tmp_path, "app/infrastructure/db/migrations/002_domain_customer_ops.sql", "domain")
    _write(tmp_path, "app/core/__pycache__/ignored.pyc", "ignored")
    _write(tmp_path, "app/presentation/view.py", "view")

    manifest_path, manifest = export_basement(
        tmp_path,
        generated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

    assert manifest_path == tmp_path / "dist" / "basement" / "manifest.json"
    assert manifest["components"] == list(BASEMENT_COMPONENTS)
    assert manifest["generated_at"] == "2026-01-02T03:04:05Z"
    paths = [entry["path"] for entry in manifest["files"]]
    assert paths == sorted(paths)
    assert "app/infrastructure/db/migrations/002_domain_customer_ops.sql" not in paths
    assert "app/core/__pycache__/ignored.pyc" not in paths

    for entry in manifest["files"]:
        exported = tmp_path / "dist" / "basement" / "files" / entry["path"]
        assert exported.exists()
        assert hashlib.sha256(exported.read_bytes()).hexdigest() == entry["sha256"]

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest


def test_file_discovery_is_explicit_and_excludes_non_basement(tmp_path):
    _write(tmp_path, "app/core/ok.py")
    _write(tmp_path, "app/modules/domain.py")
    _write(tmp_path, "config/project.yaml")

    assert [p.relative_to(tmp_path).as_posix() for p in basement_files(tmp_path)] == [
        "app/core/ok.py"
    ]
