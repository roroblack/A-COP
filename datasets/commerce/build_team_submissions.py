#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""팀원들이 낸 원본 제출본을 하나로 묶어 `_dist/` 에 넣는다.

    python datasets/commerce/build_team_submissions.py

`build_distribution.py` 는 **재현 코드와 쿠팡 산출물**을 배포하는 것이고,
이 스크립트는 **팀원 제출본 원본**을 한 덩어리로 보존하는 것이다. 목적이 달라서
따로 둔다. 둘을 한 파일에 섞으면 allowlist 가 무엇을 위한 것인지 흐려진다.

★원본 바이트를 그대로 넣는다. 이름도 안 바꾼다.
  `naver_tracking_2026-08-21_kjh` 만 확장자가 없는데, 여기서 조용히 고치면
  나중에 원본과 대조할 때 어긋난다. 매니페스트에 적기만 한다.

★건수는 파일명이 아니라 파일을 읽어서 센다.
  `naver_2026-08-21_102건_kjh.json` 은 이름이 102건인데 실제로는 101건이다.

★개인정보. 이 묶음은 팀원 본인들의 실제 구매 기록이다. 수취인·전화번호·상세주소·
  우편번호 필드는 없지만, 네이버 주문의 `DeliveryRegion` 에 배송지가 **구 단위까지**
  들어 있다. `_dist/` 는 `.gitignore` 의 `datasets/**/*.zip` 로 막혀 있어 커밋되지
  않는다. 저장소 밖으로 내보낼 때는 이 필드를 지우고 내보낸다.
"""
from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COMMERCE = Path(__file__).resolve().parent
DIST = COMMERCE / "_dist"

#: 담을 것. 폴더를 훑지 않고 이름을 적는다 — 훑으면 나중에 엉뚱한 게 딸려 들어간다.
NAVER_ORDERS = [
    ("cyw", "naver_order_history/raw/naver_2026-08-20_68건_cyw.json"),
    ("kjh", "naver_order_history/raw/naver_2026-08-21_102건_kjh.json"),
    ("syh", "naver_order_history/raw/naver_2026-08-21_44건_syh.json"),
    ("csw", "naver_order_history/raw/naver_2026-08-21_57건_csw.json"),
]
NAVER_TRACKING = [
    ("cyw", "courier_tracking/raw/_incoming_20260829/naver_tracking_2026-08-20_cyw.jsonl"),
    ("kjh", "courier_tracking/raw/_incoming_20260829/naver_tracking_2026-08-21_kjh"),
    ("csw", "courier_tracking/raw/_incoming_20260829/naver_tracking_2026-08-28_csw.jsonl"),
    ("syh", "courier_tracking/raw/_incoming_20260829/naver_tracking_2026-08-28_syh.jsonl"),
]
COUPANG_TRACKING = [
    ("cyw", "courier_tracking/raw/_incoming_20260829/coupang_tracking_20260821_195756_cyw.json"),
    ("syh", "courier_tracking/raw/_incoming_20260829/coupang_tracking_20260823_120424_syh.json"),
    ("csw", "courier_tracking/raw/_incoming_20260829/coupang_tracking_20260828_100851_csw.json"),
    ("scy", "courier_tracking/raw/_incoming_20260829/쿠팡 크롤링데이터 배송_scy.json"),
]
CONTEXT = [
    "naver_order_history/REPORT.md",
    "courier_tracking/REPORT.md",
    "naver_order_history/order_schema.json",
    "courier_tracking/tracking_schema.json",
    "build_team_submissions.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def count_orders(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data) if isinstance(data, list) else len(data.get("orders") or data.get("data") or data)


def count_tracking(path: Path) -> tuple[int, int]:
    """(질의 건수, 이력이 나온 건수). 실패는 실패로 세고 분모에서 빼지 않는다."""
    queried = with_events = 0
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    records: list = []
    if text.startswith("["):
        records = json.loads(text)
    else:
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    for r in records:
        if not isinstance(r, dict):
            continue
        queried += 1
        if r.get("events"):
            with_events += 1
    return queried, with_events


def manifest(rows: dict) -> str:
    L = ["# 팀원 제출본 묶음", "",
         "커머스 데이터 원본 제출본을 한 덩어리로 보존한 것이다.",
         "재현 코드 배포본은 `commerce_datasets_*.zip` 이며 목적이 다르다.", "",
         "생성: %s" % rows["generated_at"], "",
         "## 무엇이 들어 있나", "",
         "건수는 **파일명이 아니라 파일을 읽어 센 값**이다.", "",
         "### 네이버 주문", "",
         "| 제출자 | 파일 | 건수 |", "|---|---|---:|"]
    for who, name, n in rows["naver_orders"]:
        L.append("| %s | `%s` | %d |" % (who, name, n))
    L.append("| | **합계** | **%d** |" % sum(n for _, _, n in rows["naver_orders"]))
    L += ["", "### 네이버 택배 조회", "",
          "| 제출자 | 파일 | 질의 | 이력 나옴 |", "|---|---|---:|---:|"]
    for who, name, q, e in rows["naver_tracking"]:
        L.append("| %s | `%s` | %d | %d |" % (who, name, q, e))
    L.append("| | **합계** | **%d** | **%d** |"
             % (sum(q for _, _, q, _ in rows["naver_tracking"]),
                sum(e for _, _, _, e in rows["naver_tracking"])))
    L += ["", "### 쿠팡 배송", "",
          "네이버와 형식이 달라 따로 다뤄야 한다.", "",
          "| 제출자 | 파일 | 항목 |", "|---|---|---:|"]
    for who, name, n in rows["coupang_tracking"]:
        L.append("| %s | `%s` | %s |" % (who, name, n))
    L += ["", "## 알아 둘 것", "",
          "- `naver_2026-08-21_102건_kjh.json` 은 파일명이 102건인데 실제로는 101건이다.",
          "  이름을 바꾸지 않고 그대로 넣었다. 조용히 고치면 원본과 대조할 때 어긋난다.",
          "- `naver_tracking_2026-08-21_kjh` 만 확장자가 없다. 내용은 JSONL 이다.",
          "  이것도 이름을 바꾸지 않았다.",
          "- 택배 이력이 안 나오는 건이 많은 것은 데이터 결함이 아니다. 택배사가 배송 완료",
          "  6~12개월 뒤 기록을 지우기 때문이다. 실패로 세되 분모에서 빼지 않는다.", "",
          "## 개인정보", "",
          "팀원 본인들의 실제 구매 기록이다. 수취인·전화번호·상세주소·우편번호 필드는 없다.",
          "다만 네이버 주문의 `DeliveryRegion` 에 배송지가 **구 단위까지** 들어 있다",
          "(예: `서울특별시 노원구`). 저장소 밖으로 내보낼 때는 이 필드를 지우고 내보낸다.", "",
          "`_dist/` 는 `.gitignore` 의 `datasets/**/*.zip` 로 막혀 있어 커밋되지 않는다.", "",
          "## 무결성", "",
          "압축 후 각 항목을 원본과 바이트 단위로 대조했다. 아래는 원본의 SHA-256 이다.", "",
          "```"]
    for name, digest in rows["checksums"]:
        L.append("%s  %s" % (digest, name))
    L += ["```", ""]
    return "\n".join(L)


def build(output: Path) -> dict:
    rows = {"generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "naver_orders": [], "naver_tracking": [], "coupang_tracking": [], "checksums": []}
    entries: list[tuple[str, Path]] = []

    def add(arcname: str, path: Path) -> None:
        if not path.is_file():
            raise SystemExit("파일이 없다: %s" % path)
        entries.append((arcname, path))
        rows["checksums"].append((arcname, sha256(path)))

    for who, rel in NAVER_ORDERS:
        p = COMMERCE / rel
        add("submissions/naver_orders/" + p.name, p)
        rows["naver_orders"].append((who, p.name, count_orders(p)))
    for who, rel in NAVER_TRACKING:
        p = COMMERCE / rel
        add("submissions/naver_tracking/" + p.name, p)
        q, e = count_tracking(p)
        rows["naver_tracking"].append((who, p.name, q, e))
    for who, rel in COUPANG_TRACKING:
        p = COMMERCE / rel
        add("submissions/coupang_tracking/" + p.name, p)
        try:
            n = str(count_orders(p))
        except Exception:
            n = "형식 확인 필요"
        rows["coupang_tracking"].append((who, p.name, n))
    for rel in CONTEXT:
        p = COMMERCE / rel
        add("context/" + rel, p)

    DIST.mkdir(exist_ok=True)
    text = manifest(rows)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("MANIFEST.md", text)
        for arcname, path in entries:
            z.write(path, arcname)

    # ★넣은 것이 원본과 같은지 확인한다. 압축이 조용히 깨진 채로 배포되면
    #   나중에 원본을 지운 뒤에야 알게 된다.
    with zipfile.ZipFile(output) as z:
        for arcname, path in entries:
            if hashlib.sha256(z.read(arcname)).hexdigest().upper() != sha256(path):
                raise SystemExit("압축 결과가 원본과 다르다: %s" % arcname)
    return rows


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = DIST / ("team_submissions_%s.zip" % stamp)
    rows = build(output)
    print("만듦: %s" % output)
    print("  크기 %.1f KB · 항목 %d개 · sha256 %s"
          % (output.stat().st_size / 1024, len(rows["checksums"]) + 1, sha256(output)[:16]))
    print("  네이버 주문 %d건" % sum(n for _, _, n in rows["naver_orders"]))
    print("  네이버 택배 질의 %d건, 이력 %d건"
          % (sum(q for _, _, q, _ in rows["naver_tracking"]),
             sum(e for _, _, _, e in rows["naver_tracking"])))
    print("  쿠팡 배송 제출본 %d개" % len(rows["coupang_tracking"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
