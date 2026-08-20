"""네이버 택배조회 내부 API를 브라우저의 JSONP로 호출한다."""

from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


DATASET_ROOT = Path(__file__).resolve().parents[1]
COURIER_CODES_PATH = DATASET_ROOT / "courier_codes.json"
SEARCH_URL = (
    "https://search.naver.com/search.naver?where=nexearch&"
    "query=%ED%83%9D%EB%B0%B0%EC%A1%B0%ED%9A%8C"
)
PASSPORT_PATTERN = re.compile(
    r"passportKey[\"']?\s*[:=]\s*[\"']([^\"']{10,90})"
)
TRANSIENT_ERRORS = {"timeout", "script_error", "key_expired"}

JSONP_SCRIPT = r"""
([code, invoice, key]) => new Promise((resolve) => {
    const cb = 'cb_' + Math.random().toString(36).slice(2);
    const timer = setTimeout(() => { cleanup(); resolve('TIMEOUT'); }, 12000);
    function cleanup() {
        clearTimeout(timer);
        delete window[cb];
        if (s.parentNode) s.parentNode.removeChild(s);
    }
    window[cb] = (data) => { cleanup(); resolve(JSON.stringify(data)); };
    const s = document.createElement('script');
    s.src = 'https://ts-proxy.naver.com/ocontent/util/headerjson.naver'
        + '?callapi=parceltracking&t_code=' + code
        + '&t_invoice=' + invoice
        + '&passportKey=' + key
        + '&_callback=' + cb;
    s.onerror = () => { cleanup(); resolve('SCRIPT_ERROR'); };
    document.body.appendChild(s);
})
"""


def normalize_courier_name(value: str) -> str:
    """공백과 문장부호 및 대소문자 차이를 없앤다."""
    return "".join(character.casefold() for character in value if character.isalnum())


def load_courier_codes(path: Path = COURIER_CODES_PATH) -> list[dict[str, str]]:
    """코드가 있는 택배사만 코드 파일에서 읽는다."""
    with path.open("r", encoding="utf-8-sig") as stream:
        source = json.load(stream)
    if not isinstance(source, list):
        raise ValueError("courier_codes.json의 최상위 값은 배열이어야 합니다.")

    couriers: list[dict[str, str]] = []
    for item in source:
        if not isinstance(item, dict) or item.get("code") is None:
            continue
        text = str(item.get("text") or "").strip()
        value = str(item.get("value") or "").strip()
        code = str(item["code"]).strip()
        if text and code:
            couriers.append({"text": text, "value": value or text, "code": code})
    return couriers


def find_courier(
    name: str | None, couriers: list[dict[str, str]]
) -> dict[str, str] | None:
    """정규화한 이름의 일치 또는 충분히 긴 포함 관계를 찾는다."""
    if not name:
        return None
    wanted = normalize_courier_name(name)
    if not wanted:
        return None

    candidates: list[tuple[str, dict[str, str]]] = []
    for courier in couriers:
        for label in {courier["text"], courier["value"]}:
            normalized = normalize_courier_name(label)
            if normalized == wanted:
                return courier
            if min(len(normalized), len(wanted)) >= 3 and (
                normalized in wanted or wanted in normalized
            ):
                candidates.append((normalized, courier))
    if not candidates:
        return None
    candidates.sort(key=lambda item: len(item[0]), reverse=True)
    return candidates[0][1]


def _contains_key_expiry(value: Any) -> bool:
    """응답의 오류 문구에서 키 만료 또는 무효 상태를 찾는다."""
    if isinstance(value, dict):
        return any(_contains_key_expiry(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key_expiry(item) for item in value)
    if not isinstance(value, str):
        return False
    lowered = value.casefold()
    return ("passport" in lowered and any(word in lowered for word in ("expire", "invalid"))) or (
        "키" in value and any(word in value for word in ("만료", "유효하지"))
    )


def parse_response(
    payload: dict[str, Any], courier: str, courier_code: str, tracking_number: str
) -> dict[str, Any]:
    """API 응답을 PII가 없는 저장 형식으로 변환한다."""
    queried_at = datetime.now().astimezone().isoformat(timespec="seconds")
    common: dict[str, Any] = {
        "courier": courier,
        "courier_code": courier_code,
        "tracking_number": tracking_number,
        "status": "error",
        "item_name": str(payload.get("itemName") or ""),
        "estimate": str(payload.get("estimate") or ""),
        "level": payload.get("level") if isinstance(payload.get("level"), int) else None,
        "complete": bool(payload.get("complete")) or payload.get("completeYN") == "Y",
        "events": [],
        "queried_at": queried_at,
        "error": None,
    }

    if _contains_key_expiry(payload):
        common["error"] = "key_expired"
        return common

    result = payload.get("result")
    if result == "N":
        common["status"] = "not_found"
        common["error"] = "not_found"
        return common
    if result != "Y":
        common["error"] = "script_error"
        return common

    details = payload.get("trackingDetails")
    if not isinstance(details, list):
        details = []
    for detail in details:
        if not isinstance(detail, dict):
            continue
        common["events"].append(
            {
                "kind": str(detail.get("kind") or ""),
                "where": str(detail.get("where") or ""),
                "timeString": str(detail.get("timeString") or ""),
                "time": detail.get("time") if isinstance(detail.get("time"), int) else None,
                "level": detail.get("level") if isinstance(detail.get("level"), int) else None,
            }
        )

    if not common["events"]:
        common["status"] = "no_history"
        common["error"] = "no_history"
    else:
        common["status"] = "complete" if common["complete"] else "in_transit"
    return common


def failure_result(
    courier: str, courier_code: str, tracking_number: str, error: str
) -> dict[str, Any]:
    """브라우저 호출 단계에서 발생한 오류 결과를 만든다."""
    return {
        "courier": courier,
        "courier_code": courier_code,
        "tracking_number": tracking_number,
        "status": "error",
        "item_name": "",
        "estimate": "",
        "level": None,
        "complete": False,
        "events": [],
        "queried_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "error": error,
    }


class NaverParcelClient:
    """검색 페이지 하나에서 키 획득과 JSONP 조회를 수행한다."""

    def __init__(
        self,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        log: Callable[[str], None] | None = None,
    ) -> None:
        if delay_min < 0.5 or delay_max < 0.5:
            raise ValueError("조회 대기는 0.5초 미만으로 설정할 수 없습니다.")
        if delay_max < delay_min:
            raise ValueError("--delay-max는 --delay-min보다 작을 수 없습니다.")
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.log = log or (lambda _message: None)
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._passport_key: str | None = None
        self._failure_streak = 0
        self._query_count = 0

    def __enter__(self) -> "NaverParcelClient":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def _open_browser(self) -> None:
        if self._page is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright가 필요합니다. pip install playwright를 실행하세요."
            ) from exc
        self._playwright = sync_playwright().start()
        try:
            self._browser = self._playwright.chromium.launch(
                channel="chrome", headless=True
            )
            self._page = self._browser.new_page()
        except Exception as exc:
            self.close()
            raise RuntimeError("Chrome 브라우저를 시작하지 못했습니다.") from exc

    def acquire_passport_key(self, force: bool = False) -> str:
        """검색 페이지 HTML에서 passportKey를 한 번 얻어 재사용한다."""
        if self._passport_key and not force:
            return self._passport_key
        self._open_browser()
        try:
            self._page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30_000)
            html = self._page.content()
        except Exception as exc:
            raise RuntimeError("네이버 검색 페이지를 열지 못했습니다.") from exc
        match = PASSPORT_PATTERN.search(html)
        if not match:
            raise RuntimeError("검색 페이지에서 passportKey를 찾지 못했습니다.")
        self._passport_key = match.group(1)
        self._failure_streak = 0
        return self._passport_key

    def _wait(self) -> None:
        delay = random.uniform(self.delay_min, self.delay_max)
        self.log(f"다음 조회 전 {delay:.1f}초 대기합니다.")
        time.sleep(delay)

    def track(
        self, courier: str, courier_code: str, tracking_number: str
    ) -> dict[str, Any]:
        """필요한 대기와 키 갱신을 적용해 송장 한 건을 조회한다."""
        if self._query_count:
            self._wait()
        if self._failure_streak >= 3:
            self.log("연속 3회 실패하여 passportKey를 다시 획득합니다.")
            self.acquire_passport_key(force=True)
        else:
            self.acquire_passport_key()
        self._query_count += 1

        try:
            raw = self._page.evaluate(
                JSONP_SCRIPT, [courier_code, tracking_number, self._passport_key]
            )
        except Exception as exc:
            self.log(f"브라우저 평가 오류: {type(exc).__name__}")
            result = failure_result(
                courier, courier_code, tracking_number, "script_error"
            )
        else:
            if raw == "TIMEOUT":
                result = failure_result(courier, courier_code, tracking_number, "timeout")
            elif raw == "SCRIPT_ERROR":
                result = failure_result(
                    courier, courier_code, tracking_number, "script_error"
                )
            else:
                try:
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise ValueError("응답이 객체가 아닙니다.")
                    result = parse_response(
                        payload, courier, courier_code, tracking_number
                    )
                except (json.JSONDecodeError, TypeError, ValueError):
                    result = failure_result(
                        courier, courier_code, tracking_number, "script_error"
                    )

        if result["error"] in TRANSIENT_ERRORS:
            self._failure_streak += 1
        else:
            self._failure_streak = 0
        return result

    def close(self) -> None:
        """브라우저 관련 자원을 닫는다."""
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._page = None
        self._browser = None
        self._playwright = None
        self._passport_key = None
