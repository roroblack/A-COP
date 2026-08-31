#!/usr/bin/env python3
"""기간 필터 UI를 찾아 어떤 파라미터를 쓰는지 확인한다.

5년 이전 주문을 조회할 수 있는지 판단하기 위한 점검용이다. 수집은 하지 않는다.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
STATE_PATH = HERE / "naver_state.json"
OUT_DIR = HERE / "_inspect"
URL = "https://pay.naver.com/pc/history?serviceChannel=SHOPPING&page=1"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(storage_state=str(STATE_PATH))
        page = context.new_page()
        page.goto(URL, wait_until="networkidle", timeout=45_000)
        page.wait_for_timeout(2500)

        # 기간 관련 UI 텍스트 후보를 찾는다.
        found = []
        for el in page.locator("button, a, select, input").all()[:600]:
            try:
                t = (el.inner_text(timeout=200) or "").strip()
            except Exception:
                continue
            if any(k in t for k in ("기간", "개월", "년", "전체", "조회")) and len(t) < 30:
                found.append(t)
        report["period_ui_candidates"] = sorted(set(found))[:40]

        # 네트워크 요청에서 실제 API 파라미터를 관찰한다.
        seen: list[str] = []
        page.on("request", lambda r: seen.append(r.url) if "history" in r.url or "order" in r.url else None)
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(3000)
        report["requests"] = [u for u in seen if "api" in u or "?" in u][:25]

        # 날짜 파라미터 후보를 URL로 직접 시험한다.
        trials = {
            "startDate_endDate": "?serviceChannel=SHOPPING&page=1&startDate=20180101&endDate=20201231",
            "startYmd_endYmd": "?serviceChannel=SHOPPING&page=1&startYmd=20180101&endYmd=20201231",
            "from_to": "?serviceChannel=SHOPPING&page=1&from=20180101&to=20201231",
            "period_5y": "?serviceChannel=SHOPPING&page=1&period=5Y",
        }
        results = {}
        for name, qs in trials.items():
            time.sleep(2)
            page.goto("https://pay.naver.com/pc/history" + qs, wait_until="networkidle", timeout=45_000)
            page.wait_for_timeout(2000)
            cards = page.locator('li[class*="PaymentItem_item-payment"]').count()
            html = page.content()
            dates = re.findall(r"20\d\d\.\d\d\.\d\d", html)[:5]
            results[name] = {"url": page.url, "cards": cards, "date_hints": dates}
        report["param_trials"] = results

        context.close()
        browser.close()

    (OUT_DIR / "probe_period.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("saved probe_period.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
