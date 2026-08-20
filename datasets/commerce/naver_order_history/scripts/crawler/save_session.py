#!/usr/bin/env python3
"""로그인 창을 열고, 로그인 완료 후 세션을 JSON 파일로 저장한다.

브라우저 프로필은 비정상 종료 시 쿠키를 잃는다. 이 스크립트는 storage_state를
파일로 직접 저장하므로 그 문제가 없다.

이 스크립트는 로그인을 대신하지 않는다. 사용자가 직접 로그인하기를 기다리며,
그동안 화면을 주기적으로 캡처해 어떤 창이 열려 있는지 확인할 수 있게 한다.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROFILE_DIR = HERE / "naver_profile"
STATE_PATH = HERE / "naver_state.json"
STATUS_PATH = HERE / "_status.txt"
SHOT_PATH = HERE / "_live.png"
TARGET_URL = "https://pay.naver.com/pc/history?serviceChannel=SHOPPING&page=1"
LOGIN_HOST = "nid.naver.com"
POLL_SECONDS = 5
TIMEOUT_SECONDS = 25 * 60


def status(*lines: str) -> None:
    STATUS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    status("브라우저를 여는 중입니다.")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            args=[
                "--window-size=1200,900",
                "--window-position=100,80",
                "--new-window",
            ],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.bring_to_front()
        page.goto(TARGET_URL, wait_until="domcontentloaded")

        started = time.monotonic()
        while time.monotonic() - started < TIMEOUT_SECONDS:
            urls = []
            for p in context.pages:
                try:
                    urls.append(p.url)
                except Exception:
                    pass

            # 이 창이 실제로 무엇을 보여주는지 캡처해 둔다.
            try:
                page.screenshot(path=str(SHOT_PATH))
            except Exception:
                pass

            done = [u for u in urls if u.startswith("http") and LOGIN_HOST not in u.lower()]
            elapsed = int(time.monotonic() - started)
            status(
                f"경과 {elapsed}초",
                *[f"  탭: {u}" for u in urls],
                f"로그인 판정: {'완료' if done else '대기중'}",
            )

            if done:
                time.sleep(3)
                page.goto(TARGET_URL, wait_until="networkidle", timeout=45_000)
                time.sleep(2)
                if LOGIN_HOST in page.url.lower():
                    time.sleep(POLL_SECONDS)
                    continue

                context.storage_state(path=str(STATE_PATH))
                cards = page.locator('li[class*="PaymentItem_item-payment"]').count()
                page.screenshot(path=str(SHOT_PATH))
                status(
                    "로그인 확인 및 세션 저장 완료",
                    f"  저장 파일: {STATE_PATH.name}",
                    f"  주문 카드: {cards}건",
                    "5초 후 창을 닫습니다.",
                )
                time.sleep(5)
                context.close()
                return 0

            time.sleep(POLL_SECONDS)

        status("시간 초과. 창을 닫습니다.")
        context.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
