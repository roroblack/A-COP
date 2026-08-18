"""Server-rendered operations UI.

The API application owns registration.  Call ``mount_ui(app)`` from the
composition root; keeping this router separate preserves the S-API boundary.

★관객이 둘이다. 화면이 나뉘는 기준은 *누가 보느냐* 가 아니라 *무엇에 답하느냐* 다.

    ops_ui       /ops/**       고객사 대시보드 — **납품되는 제품**
    composer_ui  /ui/composer  제작 구성기 — `project.yaml` 을 **쓴다**

★"개발 콘솔"(조립 조회·DoD·평가 대시보드)은 이 저장소에 없다.
  `final_project_ui` 가 별도 프로그램으로 그 역할을 한다 — 이 프로세스 밖에서,
  read-only 로, `/introspection` 엔드포인트와 파일·DB 를 읽어서 붙는다.
  Composer 만 여기 남는 이유는 그것이 **이 프로젝트 자신의 설정을 쓰는** 기능이라
  read-only 외부 프로그램으로 옮길 수 없기 때문이다.
"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.core.project_config import DEFAULT_PROJECT_CONFIG, ProjectConfig, load_project_config
from app.presentation.ui.routes import tenant_router


def mount_ui(app: FastAPI, config: ProjectConfig | None = None) -> FastAPI:
    """Mount each declared UI module independently."""
    if config is None:
        selected = getattr(app.state, "project_config_path", DEFAULT_PROJECT_CONFIG)
        config = load_project_config(selected)

    landing: str | None = None
    if config.module_enabled("ops_ui"):
        app.include_router(tenant_router)
        landing = "/ops/cases"
    if config.module_enabled("composer_ui"):
        from app.presentation.ui.composer import router as composer_router
        app.include_router(composer_router)
        landing = landing or "/ui/composer"

    # ★루트가 404 였다. 개발 서버를 띄우면 브라우저가 `/` 로 열리는데
    #   빈 404 페이지가 떠서 "서버가 안 떴나" 로 읽힌다.
    #   ★UI 모듈이 전부 꺼져 있으면 만들지 않는다 — 없는 화면으로 보내면 안 된다.
    if landing is not None:
        @app.get("/", include_in_schema=False)
        def _root() -> RedirectResponse:
            return RedirectResponse(landing, status_code=307)

    return app
