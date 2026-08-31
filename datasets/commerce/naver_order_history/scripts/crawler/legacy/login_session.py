#!/usr/bin/env python3
"""로그인용 창을 열고 모든 탭의 URL을 주기적으로 기록한다.

이 스크립트는 로그인을 대신하지 않는다. 사용자가 직접 로그인하기를 기다리며,
현재 열린 탭들의 URL을 status.txt에 계속 기록해 진행 상황을 밖에서 확인할 수 있게
한다. 로그인이 감지되면 브라우저를 정상 종료해 쿠키를 디스크에 안전하게 저장한다.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROFILE_DIR = HERE / "naver_profile"
STATUS_PATH = HERE / "_status.txt"
TARGET_URL = "https://pay.naver.com/pc/history?page=1"
LOGIN_HOST = "nid.naver.com"
POLL_SECONDS = 2
TIMEOUT_SECONDS = 20 * 60


def write_status(lines: list[str]) -> None:
    STATUS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",  # 번들 Chromium 대신 설치된 Chrome을 쓴다
            args=["--window-size=1400,1000", "--window-position=80,60"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(TARGET_URL, wait_until="domcontentloaded")

        started = time.monotonic()
        while time.monotonic() - started < TIMEOUT_SECONDS:
            urls = []
            for p in context.pages:
                try:
                    urls.append(p.url)
                except Exception:
                    pass

            elapsed = int(time.monotonic() - started)
            logged_in = [u for u in urls if LOGIN_HOST not in u.lower() and u.startswith("http")]
            write_status(
                [f"경과 {elapsed}초", f"탭 {len(urls)}개"]
                + [f"  - {u}" for u in urls]
                + [f"로그인완료판정: {'예' if logged_in else '아니오'}"]
            )

            if logged_in:
                write_status(
                    [f"로그인 확인됨: {logged_in[0]}", "10초 후 정상 종료합니다."]
                )
                time.sleep(10)
                context.close()
                write_status(["정상 종료 완료. 쿠키가 프로필에 저장되었습니다."])
                return 0

            time.sleep(POLL_SECONDS)

        write_status(["시간 초과. 정상 종료합니다."])
        context.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
