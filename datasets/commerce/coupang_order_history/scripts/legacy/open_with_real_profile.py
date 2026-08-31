#!/usr/bin/env python3
"""사용자의 기존 Chrome 프로필로 쿠팡 주문목록을 연다.

로그인을 대신하지 않는다. 이미 로그인된 프로필의 세션을 그대로 쓴다.
페이지를 주기적으로 다시 열지 않으며, 신호 파일이 생길 때만 세션을 저장한다.

전제: Chrome이 완전히 종료돼 있어야 한다. 실행 중이면 프로필이 잠겨 열리지 않는다.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
CHROME_PROFILE = Path(
    r"C:\Users\playdata2\AppData\Local\Google\Chrome\User Data"
)
STATE_PATH = HERE / "coupang_state.json"
STATUS_PATH = HERE / "_status.txt"
SHOT_PATH = HERE / "_live.png"
DONE_FLAG = HERE / "_done"

TARGET_URL = "https://mc.coupang.com/ssr/desktop/order/list"
POLL_SECONDS = 3
TIMEOUT_SECONDS = 30 * 60


def status(*lines: str) -> None:
    STATUS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if DONE_FLAG.exists():
        DONE_FLAG.unlink()
    if not CHROME_PROFILE.exists():
        status(f"Chrome 프로필을 찾을 수 없습니다: {CHROME_PROFILE}")
        return 1

    status("기존 Chrome 프로필로 브라우저를 여는 중입니다.")
    with sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(
                user_data_dir=str(CHROME_PROFILE),
                headless=False,
                channel="chrome",
                args=["--window-size=1300,950", "--window-position=90,60"],
            )
        except Exception as exc:
            status(
                "프로필을 열지 못했습니다. Chrome이 완전히 종료됐는지 확인하세요.",
                f"오류: {exc}",
            )
            return 1

        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45_000)
        except Exception as exc:
            status(f"페이지 이동 실패: {exc}")

        time.sleep(4)
        try:
            page.screenshot(path=str(SHOT_PATH))
        except Exception:
            pass

        status(
            "창이 열렸습니다. 페이지를 건드리지 않습니다.",
            f"현재 URL: {page.url}",
            f"끝나면 이 파일을 만드세요: {DONE_FLAG}",
        )

        started = time.monotonic()
        while time.monotonic() - started < TIMEOUT_SECONDS:
            if DONE_FLAG.exists():
                urls = []
                for opened in context.pages:
                    try:
                        urls.append(opened.url)
                    except Exception:
                        pass
                context.storage_state(path=str(STATE_PATH))
                try:
                    page.screenshot(path=str(SHOT_PATH))
                except Exception:
                    pass
                status(
                    "세션을 저장했습니다.",
                    f"  저장 파일: {STATE_PATH.name}",
                    *[f"  탭: {u}" for u in urls],
                    "3초 후 창을 닫습니다.",
                )
                time.sleep(3)
                context.close()
                DONE_FLAG.unlink(missing_ok=True)
                return 0
            time.sleep(POLL_SECONDS)

        status("시간 초과. 창을 닫습니다.")
        context.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
