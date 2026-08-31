#!/usr/bin/env python3
"""전용 프로필로 네이버 로그인 창을 열고, 그대로 오래 유지한다.

자동으로 로그인 여부를 판단해 닫지 않는다. 사용자가 로그인을 마쳤다고 확인해 줄
때까지 창을 열어 둔다(최대 20분). 별도로 inspect_page.py를 실행해 실제 로그인
상태를 스크린샷으로 확인한다.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).resolve().parent / "naver_profile"
URL = "https://order.pay.naver.com/home"
MAX_SECONDS = 20 * 60


def main() -> int:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"프로필: {PROFILE_DIR}")
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(URL, wait_until="domcontentloaded")
        print("창을 열어 두었습니다. 이 창에서 로그인하세요. 최대 20분 유지합니다.")
        time.sleep(MAX_SECONDS)
        context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
