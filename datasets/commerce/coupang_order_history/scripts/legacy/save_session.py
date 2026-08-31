#!/usr/bin/env python3
"""쿠팡 로그인 창을 열어 두고, 사용자가 끝났다고 알릴 때까지 기다린다.

로그인을 대신하지 않는다. 그리고 로그인 중인 페이지를 건드리지 않는다.
이전 버전은 주기적으로 page.goto()를 호출해 입력을 방해했다. 이 버전은 페이지를
조작하지 않고, 신호 파일이 생기면 그때만 세션을 저장한다.

사용법:
  1) 이 스크립트를 실행하면 창이 열린다.
  2) 그 창에서 직접 로그인한다.
  3) 로그인이 끝나면 같은 폴더에 `_done` 파일을 만든다(빈 파일이면 된다).
  4) 스크립트가 세션을 저장하고 창을 닫는다.
"""

from __future__ import annotations

import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
PROFILE_DIR = HERE / "coupang_profile"
STATE_PATH = HERE / "coupang_state.json"
STATUS_PATH = HERE / "_status.txt"
DONE_FLAG = HERE / "_done"

START_URL = "https://login.coupang.com/login/login.pang"
POLL_SECONDS = 3
TIMEOUT_SECONDS = 30 * 60


def status(*lines: str) -> None:
    STATUS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    if DONE_FLAG.exists():
        DONE_FLAG.unlink()
    status("브라우저를 여는 중입니다.")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            args=["--window-size=1300,950", "--window-position=90,60"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(START_URL, wait_until="domcontentloaded", timeout=45_000)
        status(
            "창이 열렸습니다.",
            "이 창에서 직접 로그인하세요. 스크립트는 페이지를 건드리지 않습니다.",
            f"끝나면 이 파일을 만드세요: {DONE_FLAG}",
        )

        started = time.monotonic()
        while time.monotonic() - started < TIMEOUT_SECONDS:
            if DONE_FLAG.exists():
                # 페이지를 이동시키지 않고 현재 상태 그대로 저장한다.
                urls = []
                for opened in context.pages:
                    try:
                        urls.append(opened.url)
                    except Exception:
                        pass
                context.storage_state(path=str(STATE_PATH))
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
