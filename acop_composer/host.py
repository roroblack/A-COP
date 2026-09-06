"""호스트가 Composer 에게 넘기는 것들 — **패키지가 남의 저장소를 import 하지 않게** 한다.

★왜 필요한가. 이 패키지는 `final_project_cs` 같은 다른 제품에 pip 로 설치돼야
  한다. 그런데 지금까지는 `acop_basement`(sample 의 런타임 코어)를 직접 import
  했다. 그대로 cs 에 설치하면 셋이 깨진다:

    1. **등록표가 남의 것이다** — 패키지가 sample 의 `KNOWN_IMPLEMENTATION_REFS`
       를 보므로 cs 의 Team 여섯은 전부 "미등록" 422 가 난다
    2. **스키마가 남의 것이다** — sample 의 `ProjectConfig` 로 검증하는데
       `extra="forbid"` 라, cs 선언의 `response_review` 같은 칸에서 바로 실패한다
    3. **코어가 두 벌 들어간다** — 설정·DB 세션·저장소·인증을 전부 sample 코어에서
       가져오므로, cs 에 설치하면 런타임이 둘이 된다

★그래서 **호스트가 자기 것을 넘긴다.** 패키지는 이 객체가 준 것만 쓴다.
  sample 도 이제 다른 호스트와 똑같이 자기 것을 넘겨서 쓴다 — 특별대우가 없어야
  "cs 에서도 된다" 가 말이 된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol


class ConfigCodec(Protocol):
    """호스트의 **선언 스키마**. 패키지는 구조를 모르고 이것만 부른다."""

    def from_declaration(self, raw: dict[str, Any], *, source: str) -> Any:
        """raw dict 를 검증된 선언 객체로. 실패하면 `ConfigInvalid` 를 올린다."""

    def to_declaration(self, config: Any) -> dict[str, Any]:
        """검증된 선언 객체를 raw dict 로(저장·비교·응답에 쓴다)."""

    def revision(self, config: Any) -> str:
        """선언 **내용**에서 나오는 revision. 파일 mtime 이나 커밋이 아니다."""


@dataclass(frozen=True)
class Implementation:
    """카탈로그 한 줄. ★`implementation_id` 는 계약이고 `ref` 는 구현 상세다.

    UI 는 `id` 만 주고받는다 — Python 경로를 UI 가 알면 그 순간 결합이 생긴다.
    """

    id: str
    ref: str
    display_name: str
    description: str
    parameters_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class ComposerHost:
    """Composer 라우터를 만들 때 호스트가 넘기는 것 전부.

    ★여기 없는 것을 패키지가 쓰면 그게 곧 결합이다. 늘어나면 그 자체가 신호다.
    """

    #: 선언 검증·직렬화·revision — 호스트의 스키마
    codec: ConfigCodec
    #: 이 제품이 실제로 등록한 구현 목록. **호스트마다 다르다.**
    implementations: tuple[Implementation, ...] = ()
    #: 선언 파일 기본 경로(파일 모드일 때)
    default_config_path: Path | None = None
    #: 감사·이력 파일이 놓일 폴더(파일 모드일 때)
    audit_dir: Path | None = None
    #: DB 커넥션 팩토리(중앙 모드일 때만 쓴다). 없으면 중앙 모드를 못 쓴다.
    connection_factory: Callable[[], Any] | None = None
    #: 설정 조회 — `config_source`·`deployment_id` 등을 호스트가 답한다
    settings: Callable[[], Any] | None = None
    #: 가드레일 조회 — scope 목록·JWT TTL 을 호스트가 답한다
    guardrails: Callable[[], Any] | None = None
    #: 파일 모드에서 선언 저장소를 만드는 함수. ★구현은 호스트가 고른다 —
    #:  패키지는 `stores.ConfigStore` 모양만 안다.
    config_store_for: Callable[[Path], Any] | None = None
    #: 파일 모드에서 이력 저장소를 만드는 함수.
    revision_store_for: Callable[[Path], Any] | None = None
    #: 선언형 Team 파라미터 검증. 없으면 `parameters` 를 검증하지 않는다.
    validate_parameters: Callable[[dict[str, Any]], None] | None = None
    #: 부가 정보(호스트가 필요하면 채운다). 패키지는 읽지 않는다.
    extra: dict[str, Any] = field(default_factory=dict)

    def implementation(self, implementation_id: str) -> Implementation:
        for item in self.implementations:
            if item.id == implementation_id:
                return item
        raise KeyError(implementation_id)

    @property
    def known_refs(self) -> frozenset[str]:
        """이 호스트가 등록한 `implementation_ref` 전부.

        ★HTTP 경로로 임의 모듈을 import 시키지 못하게 하는 allowlist 다
          (보안 규칙이지 도메인 지식이 아니다).
        """
        return frozenset(item.ref for item in self.implementations)


class ConfigInvalid(ValueError):
    """호스트 스키마가 선언을 거부했다. 패키지는 이유를 만들지 않고 전달만 한다."""


__all__ = ["ComposerHost", "ConfigCodec", "ConfigInvalid", "Implementation"]
