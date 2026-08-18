"""콘솔이 대상에 연결할 때 사용하는 선택적 프로필."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Profile:
    name: str
    path: Path
    database_url: str | None = None
    introspection_url: str | None = None
    introspection_token: str | None = None
    contract_versions: tuple[str, ...] = field(default_factory=tuple)
    composer_url: str | None = None
    composer_issuer_secret: str | None = None


def profile_for(project: str | Path) -> Profile:
    """환경에서 선택적 연결 정보를 읽는다. 비밀값은 환경에만 둔다."""
    path = Path(project)
    versions = tuple(v.strip() for v in os.environ.get("CONSOLE_CONTRACT_VERSIONS", "v1").split(",") if v.strip())
    return Profile(
        name=path.name or str(path),
        path=path,
        database_url=os.environ.get("CONSOLE_DATABASE_URL") or None,
        introspection_url=os.environ.get("CONSOLE_INTROSPECTION_URL") or None,
        # ★대상 `/introspection` 은 scope 인증이 걸려 있다(예: `ops:introspect`).
        #   토큰 없이 실서버에 붙여 실측했더니 401 이 났다 — 헤더가 아예 안 나가고 있었다.
        introspection_token=os.environ.get("CONSOLE_INTROSPECTION_TOKEN") or None,
        contract_versions=versions,
        # ★대상의 Composer 쓰기 채널(`/composer/*`). CLAUDE.md §0.3 예외 —
        #   대상이 인증해 검증·저장하는 유일한 경로를 호출할 뿐, 파일을 직접 안 쓴다.
        composer_url=os.environ.get("CONSOLE_COMPOSER_URL") or None,
        composer_issuer_secret=os.environ.get("CONSOLE_COMPOSER_ISSUER_SECRET") or None,
    )
