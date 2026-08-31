#!/usr/bin/env python3
"""마지막 페이지 번호와 주문 상세 페이지 구조를 확인한다. 점검 전용."""

from __future__ import annotations

import html
import json
import re
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROFILE_DIR = HERE / "naver_profile"
OUT_DIR = HERE / "_inspect"
LIST_URL = "https://pay.naver.com/pc/history?serviceChannel=SHOPPING&page=1"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result: dict[str, object] = {}
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            args=["--window-size=1400,1000"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(LIST_URL, wait_until="networkidle", timeout=45_000)
        page.wait_for_timeout(2500)

        # 페이지네이션에 보이는 숫자들
        nums = []
        for el in page.locator("a, button").all():
            try:
                t = (el.inner_text(timeout=200) or "").strip()
            except Exception:
                continue
            if t.isdigit():
                nums.append(int(t))
        result["pagination_numbers_visible"] = sorted(set(nums))

        # 카드 개수와 필드 표본
        cards = page.locator('li[class*="PaymentItem_item-payment"]')
        result["cards_on_page1"] = cards.count()

        sample = []
        for i in range(min(3, cards.count())):
            c = cards.nth(i)

            def txt(sel: str) -> str | None:
                loc = c.locator(sel)
                if loc.count() == 0:
                    return None
                try:
                    return (loc.first.inner_text(timeout=800) or "").strip()
                except Exception:
                    return None

            href = None
            link = c.locator('a[class*="PaymentItem_view-detail"]')
            if link.count():
                href = link.first.get_attribute("href")

            sample.append(
                {
                    "status": txt('[class*="OrderStatus_value"]'),
                    "product": txt('[class*="ProductName_name"]'),
                    "price": txt('[class*="PaymentItem_price"]'),
                    "time": txt('[class*="PaymentItem_time"]'),
                    "detail_href": href,
                }
            )
        result["sample_cards"] = sample

        # 첫 주문 상세 페이지 구조
        if sample and sample[0]["detail_href"]:
            page.wait_for_timeout(3000)
            page.goto(sample[0]["detail_href"], wait_until="networkidle", timeout=45_000)
            page.wait_for_timeout(3000)
            result["detail_url"] = page.url
            (OUT_DIR / "detail.html").write_text(page.content(), encoding="utf-8")
            page.screenshot(path=str(OUT_DIR / "detail.png"), full_page=True)

        context.close()

    (OUT_DIR / "probe_detail.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("saved probe_detail.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
