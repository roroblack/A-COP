#!/usr/bin/env python3
"""Build the Commerce datasets ZIP with Coupang raw/processed outputs unchanged."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


COMMERCE_DIR = Path(__file__).resolve().parent
COUPANG_DIR = COMMERCE_DIR / "coupang_order_history"

ALLOWLIST = [
    "DISTRIBUTION.md",
    "coupang_order_history/REPORT.md",
    "coupang_order_history/SUCCESS_STORY.html",
    "coupang_order_history/SUCCESS_STORY_BLOGGER.html",
    "coupang_order_history/report_assets/success_story/01-network-pagination-loop.png",
    "coupang_order_history/report_assets/success_story/02-extension-installed.png",
    "coupang_order_history/report_assets/success_story/03-collector-options.png",
    "coupang_order_history/report_assets/success_story/04-collector-actions.png",
    "coupang_order_history/scripts/embed_success_story_assets.py",
    "coupang_order_history/scripts/normalize.py",
    "coupang_order_history/scripts/extension/README.md",
    "coupang_order_history/scripts/extension/background.js",
    "coupang_order_history/scripts/extension/content.js",
    "coupang_order_history/scripts/extension/manifest.json",
    "coupang_order_history/scripts/extension/popup.html",
    "coupang_order_history/scripts/extension/popup.js",
    "courier_tracking/.env.example",
    "courier_tracking/README.md",
    "courier_tracking/courier_codes.json",
    "courier_tracking/processed/.gitkeep",
    "courier_tracking/raw/.gitkeep",
    "courier_tracking/scripts/naver_parcel_api.py",
    "courier_tracking/scripts/tests/test_parse_response.py",
    "courier_tracking/scripts/track.py",
    "courier_tracking/tracking_schema.json",
    "naver_order_history/README.md",
    "naver_order_history/order_schema.json",
    "naver_order_history/processed/.gitkeep",
    "naver_order_history/raw/.gitkeep",
    "naver_order_history/scripts/crawler/.gitkeep",
    "naver_order_history/scripts/crawler/README.md",
    "naver_order_history/scripts/crawler/naver_order_crawler.py",
    "naver_order_history/scripts/crawler/requirements.txt",
    "naver_order_history/scripts/crawler/save_session.py",
    "naver_order_history/scripts/crawler/tests/test_split_months.py",
    "naver_order_history/scripts/normalize.py",
    "naver_order_history/scripts/validate.py",
    "build_distribution.py",
]


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def newest_pair() -> tuple[Path, Path]:
    raw_dir = COUPANG_DIR / "raw"
    orders = sorted(
        (path for path in raw_dir.glob("coupang_order_history_*.json") if "fail" not in path.stem.lower()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for order_path in orders:
        suffix = order_path.stem.removeprefix("coupang_order_history_")
        tracking_path = raw_dir / f"coupang_tracking_{suffix}.json"
        if tracking_path.exists():
            return order_path, tracking_path
    raise FileNotFoundError("No timestamp-matched Coupang order/tracking JSON pair found")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def build(output: Path) -> dict[str, Any]:
    order_path, tracking_path = newest_pair()
    processed_orders = COUPANG_DIR / "processed" / "orders.jsonl"
    processed_tracking = COUPANG_DIR / "processed" / "tracking.jsonl"
    stats_path = COUPANG_DIR / "preprocess_stats.json"
    data_files = [order_path, tracking_path, processed_orders, processed_tracking, stats_path]
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    archive_names = {
        order_path: f"coupang_order_history/raw/{order_path.name}",
        tracking_path: f"coupang_order_history/raw/{tracking_path.name}",
        processed_orders: "coupang_order_history/processed/orders.jsonl",
        processed_tracking: "coupang_order_history/processed/tracking.jsonl",
        stats_path: "coupang_order_history/preprocess_stats.json",
    }
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in ALLOWLIST:
            path = COMMERCE_DIR / relative
            if not path.is_file():
                raise FileNotFoundError(path)
            archive.write(path, relative.replace("\\", "/"))
        for path in data_files:
            if not path.is_file():
                raise FileNotFoundError(path)
            archive.write(path, archive_names[path])

    raw_order_payload = read_json(order_path)
    raw_tracking_payload = read_json(tracking_path)
    normalized_orders = read_jsonl(processed_orders)
    normalized_tracking = read_jsonl(processed_tracking)
    with zipfile.ZipFile(output, "r") as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC validation failed")
        for path, name in archive_names.items():
            if archive.read(name) != path.read_bytes():
                raise ValueError(f"Archive content differs from source: {name}")
        manifest = json.loads(archive.read("coupang_order_history/scripts/extension/manifest.json"))
    return {
        "zip": str(output),
        "entries": len(ALLOWLIST) + len(data_files),
        "raw_order_rows": len(raw_order_payload.get("orders", [])),
        "raw_tracking_rows": len(raw_tracking_payload),
        "processed_order_rows": len(normalized_orders),
        "processed_tracking_rows": len(normalized_tracking),
        "extension_version": manifest["version"],
        "sha256": sha256(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default_name = f"commerce_datasets_{datetime.now():%Y%m%d_%H%M%S}_with_data.zip"
    parser.add_argument("--output", type=Path, default=COMMERCE_DIR / "_dist" / default_name)
    args = parser.parse_args()
    print(json.dumps(build(args.output.resolve()), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
