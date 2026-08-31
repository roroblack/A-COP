#!/usr/bin/env python3
"""serviceChannel=SHOPPING 필터가 URL로 직접 동작하는지, 몇 페이지까지 있는지 확인한다.

수집이 아니라 구조 확인용이다. 페이지 사이에 무작위 대기를 둔다.
"""

from __future__ import annotations

import html
import json
import random
import re
import time
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROFILE_DIR = HERE / "naver_profile"
OUT_DIR = HERE / "_inspect"
BASE = "https://pay.naver.com/pc/history?serviceChannel=SHOPPING&page={page}"
MAX_PROBE_PAGES = 4


def order_ids(page_html: str) -> list[str]:
    decoded = urllib.parse.unquote(html.unescape(page_html))
    return sorted(set(re.findall(r"orders\.pay\.naver\.com/order/status/(\d+)", decoded)))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {}
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            args=["--window-size=1400,1000"],
        )
        page = context.pages[0] if context.pages else context.new_page()

        for n in range(1, MAX_PROBE_PAGES + 1):
            url = BASE.format(page=n)
            page.goto(url, wait_until="networkidle", timeout=45_000)
            page.wait_for_timeout(2500)
            ids = order_ids(page.content())
            report[f"page{n}"] = {"url": page.url, "orders": len(ids), "ids": ids}
            if n == 1:
                (OUT_DIR / "shopping_p1.html").write_text(page.content(), encoding="utf-8")
                page.screenshot(path=str(OUT_DIR / "shopping_p1.png"), full_page=True)
            if not ids:
                break
            time.sleep(random.uniform(2.0, 5.0))

        context.close()

    (OUT_DIR / "probe.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("saved probe.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
