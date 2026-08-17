from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import composition
from app.introspection import snapshot
from app.presentation.api.cases import build_router
from app.presentation.api.outbox import build_router as build_outbox_router
from app.presentation.api.composer import router as composer_write_router
from app.presentation.security import require_scope
from app.presentation.ui import mount_ui


def create_app(controller=None, classifier=None) -> FastAPI:
    injected_controller = controller is not None
    if classifier is None:
        classifier = composition.build_classifier()
    if controller is None:
        controller = composition.build_controller()
    app = FastAPI(title="A-COP S-API")
    # A classifier-only override is the legacy test seam.  Explicit controller
    # injection and the configured production path both execute the runtime.
    runtime_controller = controller if injected_controller or getattr(classifier, "__module__", "").startswith("app.composition") else None
    app.include_router(build_router(classifier, runtime_controller))
    app.include_router(build_outbox_router())
    # 운영 화면(Case/Trace/Approval/VOC). S-UI 가 소유 범위를 지켜 mount 함수만 제공하고
    # 이 한 줄 등록을 리포트로 요청했다 — 작업 리포트 §6
    mount_ui(app)
    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {
            "error": {"code": "http_error", "message": str(exc.detail)}
        }
        return JSONResponse(status_code=exc.status_code, content=detail)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": "request validation failed"}})

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception):
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error", "message": "internal server error"}})
    @app.get("/health")
    def health(): return {"status": "ok"}

    # ★basement 를 외부에서 "그대로 붙여 쓸 수 있게" 하는 표면이다.
    #   final_project_ui 같은 별도 콘솔 프로그램은 이 프로세스 안에서 파이썬을
    #   실행할 수 없다 — composition.build_registry() 를 직접 부르지 못한다.
    #   그래서 조립 상태를 **JSON 으로** 낸다. HTML 렌더링이 아니라 데이터다.
    #   /v1 아래에 두지 않는다 — case 리소스가 아니라 운영 메타데이터다(/health 와 같은 급).
    @app.get("/introspection")
    def introspection(_principal=Depends(require_scope("ops:introspect"))):
        return snapshot()

    # ★릴리스 이후에도 남는 쓰기 채널이다 — `composer_ui`(HTML 폼) 토글과 무관하게
    #   항상 등록된다. scope 로만 잠근다. HTML 페이지가 꺼져도 이 API 는 살아 있어야
    #   `final_project_ui` 가 나중에 다시 붙어 모듈을 켜고 끌 수 있다.
    app.include_router(composer_write_router)

    return app

app = create_app()
