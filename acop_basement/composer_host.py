"""이 저장소가 Composer 패키지에 넘기는 것 — **호스트 어댑터**.

★패키지(`acop_composer`)는 이제 이 저장소를 import 하지 않는다. 대신 호스트가
  자기 스키마·등록표·저장소를 넘긴다(`acop_composer.host.ComposerHost`).
  `final_project_cs` 도 자기 것을 담은 같은 모양의 객체를 만들어 넘기면 된다.

★sample 도 **특별대우 없이** 이 길로 넘긴다. 참조 구현만 지름길을 쓰면
  "cs 에서도 된다" 가 말이 안 된다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from acop_basement.core import settings as settings_module
from acop_basement.core.project_config import (
    DECLARATIVE_TEAM_REF,
    DeclarativeTeamParameters,
    ProjectConfigError,
    config_from_declaration,
)
from acop_basement.core.config_store import FileConfigStore
from acop_basement.core.revision_store import FileRevisionStore
from acop_basement.infrastructure.db.session import get_connection
from acop_composer.host import ComposerHost, ConfigInvalid, Implementation

REPO_ROOT = Path(__file__).resolve().parents[1]


class _Codec:
    """이 저장소의 선언 스키마를 패키지가 쓸 수 있는 모양으로 감싼다."""

    def from_declaration(self, raw: dict[str, Any], *, source: str) -> Any:
        try:
            return config_from_declaration(raw, source=source)
        except ProjectConfigError as exc:
            # ★패키지는 이유를 만들지 않는다. 호스트가 만든 메시지를 그대로 옮긴다.
            raise ConfigInvalid(str(exc)) from exc

    def to_declaration(self, config: Any) -> dict[str, Any]:
        payload = config.model_dump(mode="json", exclude={"revision"})
        # ★코드형 Team 의 `parameters: null` 은 빼고 낸다 — 뜻은 같지만 토글 한 번에
        #   선언 파일마다 의미 없는 한 줄이 붙어 diff 가 지저분해진다.
        for team in payload.get("teams") or []:
            if team.get("parameters") is None:
                team.pop("parameters", None)
        return payload

    def revision(self, config: Any) -> str:
        return config.revision


def _validate_parameters(raw: dict[str, Any]) -> None:
    DeclarativeTeamParameters.model_validate(raw)


#: 이 제품이 실제로 등록한 구현. ★`final_project_cs` 는 자기 여섯 개를 넣는다.
IMPLEMENTATIONS: tuple[Implementation, ...] = (
    Implementation(
        id="team.declarative.v1",
        ref=DECLARATIVE_TEAM_REF,
        display_name="선언형 Team",
        description="코드 없이 이름·역할·프롬프트·도구 목록만으로 만드는 Team. 읽기 전용이다.",
        parameters_schema=DeclarativeTeamParameters.model_json_schema(),
    ),
    Implementation(
        id="team.feedback_analytics",
        ref="app.modules.customer_ops.feedback_team:FeedbackAnalyticsTeam",
        display_name="피드백 분석 Team",
        description="VOC 분류·집계 배치를 감싼다.",
    ),
    Implementation(
        id="team.placeholder",
        ref="app.modules.placeholder:PlaceholderTeam",
        display_name="자리표시 Team",
        description="구조 검증용 최소 구현.",
    ),
)


def composer_host() -> ComposerHost:
    """이 저장소용 `ComposerHost`."""
    from acop_basement.core.project_config import DEFAULT_PROJECT_CONFIG

    return ComposerHost(
        codec=_Codec(),
        implementations=IMPLEMENTATIONS,
        default_config_path=Path(DEFAULT_PROJECT_CONFIG),
        audit_dir=REPO_ROOT / "var" / "audit",
        connection_factory=get_connection,
        settings=settings_module.get_settings,
        guardrails=settings_module.get_guardrails,
        validate_parameters=_validate_parameters,
        # ★구현은 이 저장소 것을 넘긴다. 패키지는 모양만 안다.
        config_store_for=FileConfigStore,
        revision_store_for=FileRevisionStore,
    )


__all__ = ["IMPLEMENTATIONS", "composer_host"]
