#!/usr/bin/env python3
"""결제내역 페이지에서 '쇼핑' 탭을 클릭해 그 결과 URL과 구조를 확인한다.

수집을 하지 않는 점검용 스크립트다. 탭 하나만 클릭하고 결과를 저장한다.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROFILE_DIR = HERE / "naver_profile"
OUT_DIR = HERE / "_inspect"
URL = "https://pay.naver.com/pc/history?page=1"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            args=["--window-size=1400,1000"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(URL, wait_until="networkidle", timeout=45_000)
        page.wait_for_timeout(2000)

        # 상단 필터 탭들의 텍스트를 모두 나열한다.
        print("=== 탭 후보 텍스트 ===")
        for sel in ("a", "button"):
            for el in page.locator(sel).all()[:400]:
                try:
                    t = (el.inner_text(timeout=300) or "").strip()
                except Exception:
                    continue
                if t in ("전체", "쇼핑", "현장결제", "예약·주문", "예약주문"):
                    print(f"  <{sel}> {t!r}")

        print("\n=== '쇼핑' 클릭 시도 ===")
        clicked = False
        for sel in ("a:has-text('쇼핑')", "button:has-text('쇼핑')"):
            loc = page.locator(sel)
            for i in range(loc.count()):
                el = loc.nth(i)
                try:
                    t = (el.inner_text(timeout=300) or "").strip()
                except Exception:
                    continue
                if t == "쇼핑":
                    el.click()
                    clicked = True
                    break
            if clicked:
                break

        if not clicked:
            print("  '쇼핑' 정확 일치 요소를 찾지 못했습니다.")
        else:
            page.wait_for_load_state("networkidle")
            time.sleep(3)
            print("  클릭 후 URL:", page.url)
            page.screenshot(path=str(OUT_DIR / "shopping.png"), full_page=True)
            (OUT_DIR / "shopping.html").write_text(page.content(), encoding="utf-8")
            print("  저장:", OUT_DIR / "shopping.png")

        context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
