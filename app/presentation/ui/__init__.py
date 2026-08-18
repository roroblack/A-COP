"""Server-rendered operations UI.

The API application owns registration.  Call ``mount_ui(app)`` from the
composition root; keeping this router separate preserves the S-API boundary.
"""

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.core.project_config import DEFAULT_PROJECT_CONFIG, ProjectConfig, load_project_config
from app.presentation.ui.routes import router
from app.presentation.ui.composer import router as composer_router


def mount_ui(app: FastAPI, config: ProjectConfig | None = None) -> FastAPI:
    """Mount each declared UI module independently.

    The composition root validates that enabled modules have implementations;
    this boundary performs the corresponding conditional route registration.
    ``app.state.project_config_path`` remains the test/injection seam used by
    the Composer UI.
    """
    if config is None:
        selected = getattr(app.state, "project_config_path", DEFAULT_PROJECT_CONFIG)
        config = load_project_config(selected)
    landing: str | None = None
    if config.module_enabled("ops_ui"):
        app.include_router(router)
        landing = "/ui/cases"
    if config.module_enabled("composer_ui"):
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
