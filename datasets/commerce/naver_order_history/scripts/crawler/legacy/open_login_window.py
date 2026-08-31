#!/usr/bin/env python3
"""네이버 로그인용 브라우저 창을 열어 두고, 사용자가 로그인할 때까지 기다린다.

이 스크립트는 로그인을 하지 않는다. 창만 열어 두고 사용자가 직접 아이디·비밀번호를
입력하기를 기다린다. 로그인이 감지되면 스크립트 스스로 정상적으로(강제 종료 없이)
브라우저를 닫고 종료한다. 그래야 쿠키가 프로필 디렉터리에 제대로 저장된다.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).resolve().parent / "naver_profile"
# 실제로 로그인이 필요한 보호된 페이지로 바로 이동한다.
TARGET_URL = "https://pay.naver.com/pc/history"
LOGIN_HOST = "nid.naver.com"
POLL_SECONDS = 3
INITIAL_SETTLE_SECONDS = 3
TIMEOUT_SECONDS = 20 * 60


def is_on_login_page(page) -> bool:
    return LOGIN_HOST in page.url.lower()


def main() -> int:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"프로필 디렉터리: {PROFILE_DIR}")
    print("브라우저 창을 엽니다. 그 창에서 네이버에 직접 로그인하세요.")
    print("로그인을 마치고 주문내역이 보이면 자동으로 감지해서 창을 닫습니다.")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        time.sleep(INITIAL_SETTLE_SECONDS)

        started = time.monotonic()
        while time.monotonic() - started < TIMEOUT_SECONDS:
            if not is_on_login_page(page):
                print("현재 URL:", page.url)
                print("로그인이 확인된 것으로 보입니다. 10초 후 창을 정상 종료합니다.")
                print("(잘못 감지된 것 같으면 지금 알려주세요.)")
                time.sleep(10)
                context.close()
                print("정상 종료했습니다. 이제 페이지를 다시 확인할 수 있습니다.")
                return 0
            time.sleep(POLL_SECONDS)

        print("시간 초과(20분). 정상 종료합니다.", file=sys.stderr)
        context.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
