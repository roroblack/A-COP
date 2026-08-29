"""Extract the K-Shopping subset from AI Hub 30716 and map it onto A-COP's
order/shipping/return/exchange intent+issue_code taxonomy.

Usage:
    python scripts/extract_and_map.py

Reads the 7 K-Shopping zips already separated by filename under
raw/01.데이터/1.Training/라벨링데이터_231222_add/ (and the matching
2.Validation batch, if present). Writes processed/kshopping_sample.jsonl,
processed/category_mapping.json, processed/stats.json.

AS and 업무처리 categories are deliberately excluded — they don't map
cleanly onto A-COP's five intents and forcing them into "other" would
misrepresent what the data actually says (see REPORT.md).
"""
from __future__ import annotations

import json
import random
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "01.데이터"
PROCESSED = ROOT / "processed"
SEED = 7
SAMPLE_PER_CATEGORY = 300

CATEGORY_TO_INTENT = {
    "주문": "order",
    "결제": "order",
    "배송": "shipping",
    "반품": "return",
    "교환": "exchange",
}
EXCLUDED_CATEGORIES = {"AS", "업무처리"}

ISSUE_CODE_RULES: dict[str, tuple[str, tuple[str, ...]]] = {
    # issue_code -> (required intent prefix, keyword patterns to match against
    # 고객의도 + 고객질문(요청) concatenated text)
    "order_payment_failed": ("order", ("결제실패", "결제오류", "결제안됨", "입금실패", "입금안됨", "승인거부", "승인안됨")),
    "order_duplicate_charge": ("order", ("중복결제", "중복입금", "두번결제", "이중결제")),
    "order_change_or_cancel": ("order", ("주문취소", "취소요청", "주문변경", "변경요청", "옵션변경", "수량변경")),
    "shipping_delayed": ("shipping", ("배송지연", "출고지연", "발송지연", "늦어", "언제와", "언제오")),
    "shipping_delivered_not_received": ("shipping", ("미수령", "못받", "안왔", "안옴", "수령안됨", "받지못")),
    "return_quantity_exceeded": ("return", ("수량초과", "초과반품", "수량오기재", "수량정정")),
    "return_fee_or_period": ("return", ("반품배송비", "반품비", "반품기간", "반품기한", "청약철회기한", "왕복배송비")),
    "exchange_stock_or_period": ("exchange", ("재고확인", "재고없", "품절", "교환기한", "교환기간", "교환신청기한")),
}
# order_other / shipping_other / return_other / exchange_other are the
# per-intent fallback when no specific rule matches.
FALLBACK_ISSUE_CODE = {
    "order": "order_other",
    "shipping": "shipping_other",
    "return": "return_other",
    "exchange": "exchange_other",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _match_issue_code(intent: str, customer_intent_field: str, question_text: str) -> str | None:
    haystack = _normalize(customer_intent_field) + _normalize(question_text)
    for issue_code, (required_intent, patterns) in ISSUE_CODE_RULES.items():
        if required_intent != intent:
            continue
        if any(pattern in haystack for pattern in patterns):
            return issue_code
    # No specific pattern matched. Use the per-intent fallback only when the
    # customer_intent field is non-trivially short/generic-looking; otherwise
    # leave it null (genuinely ambiguous, don't force-fit).
    if customer_intent_field and len(customer_intent_field) <= 12:
        return FALLBACK_ISSUE_CODE.get(intent)
    return None


def _find_category_zip(category: str) -> list[Path]:
    pattern = f"*K쇼핑_{category}_*.zip"
    return sorted(RAW.glob(f"*/*/{pattern}")) + sorted(RAW.glob(f"*/{pattern}"))


def _iter_customer_intent_turns(zip_path: Path):
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        with zf.open(names[0]) as fh:
            records = json.load(fh)
    for rec in records:
        if rec.get("화자") != "고객":
            continue
        if rec.get("QA") != "Q":
            continue
        intent_field = (rec.get("고객의도") or "").strip()
        question = (rec.get("고객질문(요청)") or "").strip()
        if not intent_field and not question:
            continue
        yield rec, intent_field, question


def main() -> None:
    random.seed(SEED)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    stats: dict[str, dict] = {}
    mapping_examples: dict[str, list[str]] = defaultdict(list)
    sample_rows: list[dict] = []

    for category in list(CATEGORY_TO_INTENT) + sorted(EXCLUDED_CATEGORIES):
        zips = _find_category_zip(category)
        if not zips:
            stats[category] = {"error": "zip not found"}
            continue
        total_records = 0
        customer_intent_turns = 0
        turns: list[tuple[dict, str, str]] = []
        for zpath in zips:
            with zipfile.ZipFile(zpath) as zf:
                names = zf.namelist()
                with zf.open(names[0]) as fh:
                    total_records += len(json.load(fh))
            for rec, intent_field, question in _iter_customer_intent_turns(zpath):
                customer_intent_turns += 1
                turns.append((rec, intent_field, question))

        if category in EXCLUDED_CATEGORIES:
            stats[category] = {
                "mapped_intent": None,
                "total_records": total_records,
                "customer_intent_turns": customer_intent_turns,
                "excluded_reason": "no clean mapping onto order/shipping/return/exchange; "
                                   "forcing into 'other' would misrepresent the data",
            }
            continue

        intent = CATEGORY_TO_INTENT[category]
        random.shuffle(turns)
        sampled = turns[:SAMPLE_PER_CATEGORY]
        issue_code_counts: Counter[str] = Counter()
        for rec, intent_field, question in sampled:
            issue_code = _match_issue_code(intent, intent_field, question)
            issue_code_counts[issue_code or "null"] += 1
            if issue_code and len(mapping_examples[issue_code]) < 5:
                mapping_examples[issue_code].append(intent_field or question[:40])
            sample_rows.append({
                "source_category": category,
                "customer_turn_text": question or None,
                "raw_intent_field": intent_field or None,
                "mapped_intent": intent,
                "mapped_issue_code": issue_code,
            })

        stats[category] = {
            "mapped_intent": intent,
            "total_records": total_records,
            "customer_intent_turns": customer_intent_turns,
            "sampled": len(sampled),
            "issue_code_counts": dict(issue_code_counts),
        }

    with (PROCESSED / "kshopping_sample.jsonl").open("w", encoding="utf-8") as f:
        for row in sample_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    category_mapping = {
        "category_to_intent": CATEGORY_TO_INTENT,
        "excluded_categories": sorted(EXCLUDED_CATEGORIES),
        "issue_code_rules": {k: v[1] for k, v in ISSUE_CODE_RULES.items()},
        "fallback_issue_code": FALLBACK_ISSUE_CODE,
        "matched_examples": dict(mapping_examples),
    }
    (PROCESSED / "category_mapping.json").write_text(
        json.dumps(category_mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    (PROCESSED / "stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"sample_rows": len(sample_rows), "categories": list(stats)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
