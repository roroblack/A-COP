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
    )
