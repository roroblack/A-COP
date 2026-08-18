"""★관객 경계 — 화면 배치가 아니라 **보안·정보 경계**다.

    /ops/**         고객사 대시보드 — 쇼핑몰 운영자가 자기 CS 를 본다. **납품되는 제품**
    /ui/composer    구성기 — `project.yaml` 을 쓴다. 이것도 제품의 일부다
    /introspection  조립 상태를 JSON 으로 낸다. **외부 개발 콘솔**(final_project_ui)이
                    이 프로세스 안에서 파이썬을 실행하지 않고 붙는 유일한 통로

★"개발 콘솔"(조립 조회·DoD·평가 대시보드)은 이 저장소에 없다.
  한때 `/ui/admin`·`/ui/quality`·`/ui/experiments` 로 이 저장소 안에 지었다가,
  `final_project_ui` 가 별도 프로그램으로 만들어지면서 **중복·드리프트 위험**이 됐다.
  지웠다 — basement 는 제품 기능만 갖는다.

★검사하지 않는 규칙은 지켜지지 않는다. 그래서 경계를 테스트로 못 박는다.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation.ui import mount_ui

TENANT_PATHS = ("/ops/cases", "/ops/approvals", "/ops/voc")


def _client(path: Path) -> TestClient:
    app = FastAPI()
    app.state.project_config_path = path
    mount_ui(app)
    return TestClient(app)


def _write(tmp: Path, **modules) -> Path:
    data = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    for name, enabled in modules.items():
        data["modules"].setdefault(name, {})["enabled"] = enabled
    path = tmp / "project.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture()
def workdir():
    path = Path(".audience-" + uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


def test_composer_can_be_shipped_disabled(workdir):
    """★납품 시 구성기를 끈다. 고객사 화면은 그대로 산다."""
    client = _client(_write(workdir, ops_ui=True, composer_ui=False))
    assert client.get("/ui/composer").status_code == 404
    for path in TENANT_PATHS:
        assert client.get(path).status_code == 200, f"{path} 가 죽었다"


def test_tenant_ui_can_be_disabled_independently(workdir):
    """반대 방향 — 구성만 열어 두고 고객 화면은 안 띄우는 구성."""
    client = _client(_write(workdir, ops_ui=False, composer_ui=True))
    for path in TENANT_PATHS:
        assert client.get(path).status_code == 404
    assert client.get("/ui/composer").status_code == 200


def test_composer_navigation_does_not_leak_into_tenant_screens(workdir):
    """★고객사에게 우리 사정(구성기)이 보이면 안 된다."""
    client = _client(_write(workdir, ops_ui=True, composer_ui=True))
    tenant_page = client.get("/ops/cases").text
    assert "Composer" not in tenant_page, "고객사 화면에 구성기 메뉴가 보인다"


def test_tenant_screens_are_scoped_by_tenant(workdir):
    """★고객사 화면의 조회는 전부 tenant 조건을 건다.

    소스를 읽어 확인한다 — 조건 없는 조회는 그 자체가 보안 결함이다.
    """
    source = Path("app/presentation/ui/routes.py").read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        if "FROM customer_cases" in stripped or "FROM action_requests" in stripped \
                or "FROM feedback_analytics_reports" in stripped:
            assert "tenant_id=%s" in stripped, f"tenant 조건 없는 조회: {stripped[:90]}"
