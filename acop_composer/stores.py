"""Composer 가 쓰는 저장소의 **모양**만 정의한다 — 구현은 호스트가 넘긴다.

★왜 Protocol 만인가. 구현(`FileConfigStore`·`PostgresConfigStore` 등)은 호스트
  코어에 남는다. `final_project_sample` 의 대상 런타임이 중앙 모드에서 **자기
  선언을 읽을 때** 같은 구현을 쓰기 때문이다
  (`acop_basement/application/config_source.py`). 구현을 이 패키지로 올리면
  호스트가 선택 패키지를 역으로 의존하게 되고, **Composer 를 안 깔면 대상이
  중앙에서 설정을 못 읽는다** — 결합 방향이 뒤집힌다(2026-09-06 판단).

★그래서 패키지는 "이런 모양이면 된다" 만 말하고, 무엇을 쓸지는 호스트가 정한다.
  `final_project_cs` 는 자기 구현을 넘기면 된다.
"""
from __future__ import annotations

from typing import Any, Protocol


class StoreError(RuntimeError):
    """저장소가 요청을 수행하지 못했다. 호스트 예외를 이 모양으로 올린다."""


class RevisionMismatch(StoreError):
    """조건부 쓰기가 거부됐다 — 그 사이 남이 썼다.

    ★저장소가 **최종 판정자**다. 프로세스 락을 통과했어도 여기서 질 수 있다.
    """

    def __init__(self, current_revision: str) -> None:
        super().__init__(f"revision mismatch: {current_revision}")
        self.current_revision = current_revision


class ConfigStore(Protocol):
    """선언을 읽고 **조건부로** 쓴다."""

    def read(self) -> dict[str, Any]:
        """현재 선언(raw dict). 대상이 등록돼 있지 않으면 `StoreError`."""

    def write(self, declaration: dict[str, Any], *, base_revision: str,
              new_revision: str) -> None:
        """`base_revision` 이 맞을 때만 쓴다. 아니면 `RevisionMismatch`."""


class RevisionStore(Protocol):
    """선언 이력. ★append-only 다 — 고치거나 지우지 않는다."""

    def append(self, entry: dict[str, Any]) -> None: ...

    def recent(self, limit: int) -> list[dict[str, Any]]: ...

    def find(self, revision: str) -> dict[str, Any] | None: ...


__all__ = ["ConfigStore", "RevisionMismatch", "RevisionStore", "StoreError"]
