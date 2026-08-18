"""구조도가 **현재 선언을 따라가는지** 검사한다.

★그림이 하드코딩되면 조립과 어긋나도 아무도 모른다.
  "vector_rag 를 껐는데 구조도에는 켜져 있다" 가 되면 그림이 거짓말을 한다.
  그래서 검사하는 것은 "그림이 그려진다" 가 아니라 **"선언을 반영한다"** 이다.
"""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.presentation.ui import mount_ui


def _client(path: Path) -> TestClient:
    app = FastAPI()
    app.state.project_config_path = path
    mount_ui(app)
    return TestClient(app)


def _write(tmp: Path, **module_overrides) -> Path:
    data = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    data["modules"]["composer_ui"]["enabled"] = True
    for name, enabled in module_overrides.items():
        data["modules"][name]["enabled"] = enabled
    path = tmp / "project.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture()
def workdir():
    path = Path(".composer-structure-" + uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        for child in path.iterdir():
            child.unlink()
        path.rmdir()


def _node(html: str, name: str) -> str:
    """구조도에서 해당 노드의 <li> 조각을 꺼낸다."""
    match = re.search(r"<li class='node[^']*'>(?:(?!</li>).)*?" + re.escape(name)
                      + r"(?:(?!</li>).)*?</li>", html, re.S)
    assert match, f"구조도에 '{name}' 노드가 없다"
    return match.group(0)


def test_structure_follows_the_declaration(workdir):
    on = _client(_write(workdir, vector_rag=True)).get("/ui/composer").text
    assert "node--off" not in _node(on, "vector_rag")
    assert "켜짐" in _node(on, "vector_rag")

    off = _client(_write(workdir, vector_rag=False)).get("/ui/composer").text
    # ★껐으면 구조도에서도 꺼져 보여야 한다
    assert "node--off" in _node(off, "vector_rag")
    assert "꺼짐" in _node(off, "vector_rag")


def test_components_are_never_marked_toggleable(workdir):
    html = _client(_write(workdir)).get("/ui/composer").text
    for fixed in ("transition_case()", "Context Broker", "Team Registry", "Outbox"):
        node = _node(html, fixed)
        assert "node--component" in node, f"{fixed} 는 컴포넌트로 그려져야 한다"
        # ★컴포넌트에 켜짐/꺼짐이 붙으면 끌 수 있는 것처럼 읽힌다
        assert "꺼짐" not in node


def test_stages_are_in_execution_order(workdir):
    html = _client(_write(workdir)).get("/ui/composer").text
    # ★페이지 전체에서 찾으면 안 된다 — 같은 낱말이 모듈 목록·컴포넌트 목록에도 있어
    #   구조도가 아닌 곳의 위치를 집는다 (처음에 이렇게 짰다가 이 테스트가 잡았다).
    titles = re.findall(r"<h3 class='stage__title'>(.*?)</h3>", html, re.S)
    assert titles, "구조도 단계 제목을 못 찾았다"
    expected = ["입력", "Case 생성 · 상태 전이", "분류", "컨텍스트 조립", "라우팅",
                "실행", "Agent Team", "제안 · 승인", "발행", "관측"]
    assert titles == expected, f"구조도 단계가 실행 순서가 아니다: {titles}"


def test_sections_and_stages_can_be_folded(workdir):
    """★접고 펼 수 있어야 한다 — 10단계가 통째로 펼쳐지면 원하는 곳을 찾기 어렵다."""
    html = _client(_write(workdir)).get("/ui/composer").text
    # 큰 덩어리는 접이식 카드
    assert html.count("card--fold") >= 5
    # 단계마다 개별로 접힌다
    assert html.count("stage__body") >= 10
    # ★컴포넌트 목록은 기본 접힘, 나머지는 펼침 (접힌 채로 두면 있는 줄도 모른다)
    fold_open = re.findall(r"<details class='card card--fold[^']*'( open)?>", html)
    assert fold_open.count("") == 1, "기본 접힘은 컴포넌트 목록 하나여야 한다"


def test_save_button_comes_before_the_read_only_sections(workdir):
    """★고치는 것 → 저장 → 읽을 것. 이 순서다.

    읽기 전용 목록이 저장 버튼 위에 있으면, 편집을 끝내고 저장하려는 사람이
    바꿀 수도 없는 목록을 지나쳐 내려가야 한다.
    """
    html = _client(_write(workdir)).get("/ui/composer").text
    save = html.index("name='save'")
    assert save < html.index("구조 — 실행 순서"), "저장 버튼이 구조도보다 뒤에 있다"
    assert save < html.index("컴포넌트 (읽기 전용)"), "저장 버튼이 컴포넌트 목록보다 뒤에 있다"
    # ★읽기 전용 덩어리는 form 밖이어야 한다 — 입력이 없는데 폼에 들어갈 이유가 없다
    assert html.index("</form>") < html.index("컴포넌트 (읽기 전용)")


def test_editable_sections_are_inside_the_form(workdir):
    html = _client(_write(workdir)).get("/ui/composer").text
    form = html.index("</form>")
    for editable in ("module_vector_rag", "port_team_executor", "team_id_0", "add_team"):
        assert html.index(editable) < form, f"{editable} 가 form 밖에 있다"


def test_diagram_text_is_readable_without_css(workdir):
    """★마크업만으로도 읽혀야 한다.

    전에는 이름·배지·설명이 구분자 없이 붙어 `REST /v1고정쓰기 경로` 로 뽑혔다.
    CSS 가 간격을 주지만 복사·스크린리더·텍스트 추출은 마크업만 본다.
    """
    html = _client(_write(workdir)).get("/ui/composer").text
    assert "<span class='node__kind'> — " in html


def test_stage_numbers_are_not_duplicated(workdir):
    """★<ol> 이면 브라우저 자동 번호와 stage__n 배지가 겹쳐 '1. 1' 이 된다."""
    html = _client(_write(workdir)).get("/ui/composer").text
    assert "<ul class='flow'>" in html
    assert "<ol class='flow'>" not in html


def test_active_teams_are_counted_from_the_declaration(workdir):
    html = _client(_write(workdir)).get("/ui/composer").text
    data = yaml.safe_load(Path("config/project.yaml").read_text(encoding="utf-8"))
    active = sum(1 for t in data["teams"] if t["active"])
    assert f"지금 {active}개 라우팅" in html
