"""대상의 introspection HTTP 응답을 읽는 read-only 어댑터."""
from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LiveRead:
    status: str
    value: dict | None = None
    detail: str = ""


def read_introspection(url: str | None, supported_versions: tuple[str, ...] = (),
                        token: str | None = None) -> LiveRead:
    if not url:
        return LiveRead("연결 안 함", detail="introspection_url 이 프로필에 없음")
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        request = Request(url, method="GET", headers=headers)
        with urlopen(request, timeout=3) as response:
            if response.status == 404:
                return LiveRead("그 경로가 없음", detail=url)
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            return LiveRead("그 경로가 없음", detail=url)
        if exc.code in (401, 403):
            # ★"대상이 응답하지 않음" 으로 뭉치면 사실이 아니다 — 대상은 응답했다,
            #   인증이 안 됐을 뿐이다. 실측(scope `ops:introspect`)으로 확인했다.
            detail = "introspection_token 이 프로필에 없거나 scope 가 안 맞음" if not token else f"HTTP {exc.code}"
            return LiveRead("인증 실패", detail=detail)
        return LiveRead("대상이 응답하지 않음", detail=f"HTTP {exc.code}")
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return LiveRead("대상이 응답하지 않음", detail=str(exc))
    if not isinstance(raw, dict):
        return LiveRead("계약 버전 모름", detail="응답이 객체가 아님")
    version = raw.get("contract_version")
    if version not in supported_versions:
        return LiveRead("계약 버전 모름", value=raw, detail=f"contract_version={version!r}")
    return LiveRead("읽음", value=raw, detail=f"contract_version={version}")
