from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation.ui import mount_ui


def _app(path: Path) -> TestClient:
    app = FastAPI()
    app.state.project_config_path = path
    mount_ui(app)
    return TestClient(app)


def _declaration(tmp_path: Path, *, enabled: bool = True) -> Path:
    source = Path("config/project.yaml")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    data["modules"]["composer_ui"]["enabled"] = enabled
    path = tmp_path / "project.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture()
def config_dir():
    path = Path(".composer-e2e-" + uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


def test_composer_is_404_when_disabled(config_dir):
    """★끄면 404 인지를 검사한다 — 저장소 기본값이 무엇인지를 검사하는 게 아니다.

    전에는 `config/project.yaml` 을 그대로 읽어 404 를 단언했다. 그래서
    **이 테스트를 통과시키려면 저장소 기본값이 꺼짐이어야 했고**,
    정작 쓰려는 구성기가 계속 404 였다.

    검사하려는 성질은 "선언이 false 면 라우트가 없다" 이지
    "저장소 기본값이 false 다" 가 아니다. 임시 선언으로 그 성질만 검사한다.
    """
    client = _app(_declaration(config_dir, enabled=False))
    assert client.get("/ui/composer").status_code == 404


def test_ui_modules_are_independent(config_dir):
    path = _declaration(config_dir)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["modules"]["ops_ui"]["enabled"] = False
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    client = _app(path)
    assert client.get("/ui/cases").status_code == 404
    assert client.get("/ui/composer").status_code == 200


def test_enabled_composer_shows_current_teams_and_read_only_components(config_dir):
    client = _app(_declaration(config_dir))
    response = client.get("/ui/composer")
    assert response.status_code == 200
    assert "order_shipping" in response.text
    assert "return_exchange" in response.text
    assert response.text.count("type='checkbox'") >= 9
    assert "컴포넌트 (읽기 전용)" in response.text
    assert "Case lifecycle" in response.text
    assert "name='component" not in response.text


def test_invalid_active_team_is_not_saved(config_dir):
    path = _declaration(config_dir)
    before = path.read_bytes()
    client = _app(path)
    response = client.post("/ui/composer", data={
        "module_vector_rag": "on", "module_graph_store": "on", "module_mcp": "on",
        "module_voc": "on", "module_ops_ui": "on", "module_composer_ui": "on",
        "port_team_executor": "local", "port_message_broker": "outbox", "port_graph_store": "sql",
        "team_id_0": "order_shipping", "active_0": "on",
        "implementation_ref_0": "app.nonexistent:Missing",
        "team_id_1": "return_exchange", "active_1": "on",
        "implementation_ref_1": "app.modules.customer_ops:ReturnExchangeTeam",
        "save": "1",
    })
    assert response.status_code == 200
    assert "cannot be imported" in response.text
    assert path.read_bytes() == before
    assert not path.with_suffix(".bak").exists()


def test_added_team_defaults_to_inactive_and_save_creates_backup(config_dir):
    path = _declaration(config_dir)
    client = _app(path)
    added = client.post("/ui/composer", data={
        "module_vector_rag": "on", "module_graph_store": "on", "module_mcp": "on",
        "module_voc": "on", "module_ops_ui": "on", "module_composer_ui": "on",
        "port_team_executor": "local", "port_message_broker": "outbox", "port_graph_store": "sql",
        "team_id_0": "order_shipping", "active_0": "on",
        "implementation_ref_0": "app.modules.customer_ops:OrderShippingTeam",
        "team_id_1": "return_exchange", "active_1": "on",
        "implementation_ref_1": "app.modules.customer_ops:ReturnExchangeTeam",
        "add_team": "1",
    })
    assert "미구현 — 등록되지만 라우팅되지 않음" in added.text
    assert "name='active_2'" in added.text and "name='active_2' checked" not in added.text

    saved = client.post("/ui/composer", data={
        "module_vector_rag": "on", "module_graph_store": "on", "module_mcp": "on",
        "module_voc": "on", "module_ops_ui": "on", "module_composer_ui": "on",
        "port_team_executor": "local", "port_message_broker": "outbox", "port_graph_store": "sql",
        "team_id_0": "order_shipping", "active_0": "on",
        "implementation_ref_0": "app.modules.customer_ops:OrderShippingTeam",
        "team_id_1": "return_exchange", "active_1": "on",
        "implementation_ref_1": "app.modules.customer_ops:ReturnExchangeTeam",
        "team_id_2": "new_team", "implementation_ref_2": "app.modules.placeholder:PlaceholderTeam",
        "save": "1",
    })
    assert saved.status_code == 200
    assert "저장했습니다" in saved.text
    assert path.with_suffix(".yaml.bak").exists()
    declaration = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert declaration["teams"][2]["active"] is False
