"""Composer 쓰기 채널 — `/composer/validate`, `/composer/apply`.

★이게 릴리스 이후 콘솔이 모듈을 켜고 끄는 방법이다.

  `/ui/composer` HTML 폼은 **개발 중에만** 켠다(`composer_ui` 모듈 토글, 릴리스 시 끈다).
  이 두 엔드포인트는 **모듈 토글과 무관하게 항상 켜져 있다** — scope 로만 잠근다.
  HTML 페이지가 없어져도 이 채널은 남아서, `final_project_ui` 같은 외부 콘솔이
  나중에 이걸 호출해 구성을 바꾼다.

★콘솔은 `ProjectConfig` 를 import 하지 않는다. raw dict 를 보내고, 이 서버가
  검증해서 결과를 JSON 으로 돌려줄 뿐이다 — "포크" 가 아니다
  (`final_project_ui/CLAUDE.md` §0.2 가 금지하는 것이 바로 검증 모델 복제다).

★`/v1` 아래에 두지 않는다 — case 리소스가 아니라 조립 관리 메타데이터다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from app.application.composer_service import RevisionConflict, apply_candidate, read_current, validate_candidate
from app.core.project_config import DEFAULT_PROJECT_CONFIG, ProjectConfigError
from app.presentation.security import require_scope

router = APIRouter(prefix="/composer", tags=["composer-write"])


def _path(request: Request) -> Path:
    """읽고 쓸 선언 파일. ★HTML 라우터(`app/presentation/ui/composer.py`)와
    같은 `app.state.project_config_path` 관례를 따른다 — 테스트가 실제
    `config/project.yaml` 을 건드리지 않고 임시 선언으로 이 API 를 검사할 수 있다."""
    selected = getattr(request.app.state, "project_config_path", DEFAULT_PROJECT_CONFIG)
    return Path(selected)


class CandidatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: dict[str, Any]


class ApplyPayload(CandidatePayload):
    #: ★적용 직전에 서버가 다시 확인한다. 이게 없으면 "마지막에 쓴 사람이 이긴다" 가
    #:   조용히 일어난다 — 남이 그 사이 바꾼 걸 알아채지 못하고 덮어쓴다.
    base_revision: str


def _error(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": {"code": code, "message": message, **extra}})


@router.get("/current", tags=["composer-write"])
def current(request: Request, _principal=Depends(require_scope("composer:write"))) -> dict[str, Any]:
    """지금 파일의 revision·내용. apply 를 보내기 전 base_revision 을 여기서 얻는다."""
    config = read_current(_path(request))
    return {"revision": config.revision, "config": config.model_dump(mode="json", exclude={"revision"})}


@router.post("/validate")
def validate(payload: CandidatePayload, request: Request,
            _principal=Depends(require_scope("composer:write"))) -> dict[str, Any]:
    """후보를 검증만 한다. **파일을 바꾸지 않는다.**

    ★활성 Team 의 `implementation_ref` 를 실제로 import 해서 검증한다
      (`ProjectConfigError` 를 통해). 이건 **이미 그 서버 프로세스에 설치된**
      모듈만 로드할 수 있다 — 원격에서 새 코드를 주입하는 경로가 아니다.
      임의 문자열을 보내도 `importlib.import_module` 이 없는 모듈이면 그냥 실패한다.
    """
    result = validate_candidate(payload.config, path=_path(request))
    if not result.valid:
        return {"valid": False, "errors": result.errors}
    return {"valid": True, "errors": [], "revision": result.config.revision}


@router.post("/apply")
def apply(payload: ApplyPayload, request: Request,
         _principal=Depends(require_scope("composer:write"))) -> dict[str, Any]:
    """검증 통과 + revision 일치 시에만 **원자적으로** 쓴다."""
    try:
        applied = apply_candidate(payload.config, base_revision=payload.base_revision, path=_path(request))
    except RevisionConflict as exc:
        # ★409 다. 400 이 아니다 — 요청 자체는 유효했고, 그 사이 상태가 바뀐 것이다.
        raise _error(409, "revision_conflict",
                     "다른 변경이 먼저 적용됐다. 최신 구성을 다시 읽고 다시 시도하라.",
                     current_revision=exc.current_revision) from exc
    except ProjectConfigError as exc:
        raise _error(422, "invalid_declaration", str(exc)) from exc
    return {"revision": applied.revision, "applied": True}
