#!/usr/bin/env python3
"""저장된 로그인 프로필로 결제내역 페이지를 열어 구조를 점검한다.

선택자를 확정하기 위한 점검용 스크립트다. 클릭이나 입력 없이 페이지를 열어
스크린샷과 HTML만 저장한다.
"""

from __future__ import annotations

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
        page.wait_for_timeout(3000)

        print("현재 URL:", page.url)
        print("제목:", page.title())

        page.screenshot(path=str(OUT_DIR / "history.png"), full_page=True)
        (OUT_DIR / "history.html").write_text(page.content(), encoding="utf-8")
        print("저장:", OUT_DIR / "history.png")

        context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
