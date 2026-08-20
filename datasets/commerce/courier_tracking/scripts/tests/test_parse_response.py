"""네이버 응답 파싱과 PII 제거를 네트워크 없이 검증한다."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from naver_parcel_api import (  # noqa: E402
    find_courier,
    load_courier_codes,
    parse_response,
)


ACTUAL_RESPONSE = {
    "result": "Y",
    "senderName": "보내는 사람",
    "receiverName": "받는 사람",
    "receiverAddr": "서울시 비공개 주소",
    "recipient": "수취인",
    "itemName": "엑츠 베이킹소다 3L",
    "invoiceNo": "540885631633",
    "estimate": "13~15시",
    "level": 6,
    "complete": True,
    "savedTime": "Aug 20, 2026 3:11:14 PM",
    "completeYN": "Y",
    "trackingDetails": [
        {
            "time": 1782869678000,
            "timeString": "2026-07-01 10:34:38",
            "where": "장안대리점",
            "kind": "집화처리",
            "telno": "010-0000-0000",
            "telno2": "02-1588-1255",
            "level": 2,
            "manName": "배송 기사",
            "manPic": "https://example.invalid/private.jpg",
        },
        {
            "time": 1782905183000,
            "timeString": "2026-07-01 20:26:23",
            "where": "장안B",
            "kind": "간선상차",
            "telno": "02-1588-1255",
            "telno2": "",
            "level": 3,
            "manName": "",
            "manPic": "",
        },
    ],
}


class ParseResponseTest(unittest.TestCase):
    def test_courier_codes_and_normalized_matching(self) -> None:
        couriers = load_courier_codes()
        self.assertTrue(all(courier["code"] for courier in couriers))
        courier = find_courier(" cj 대한통운 택배 ", couriers)
        self.assertIsNotNone(courier)
        self.assertEqual(courier["code"], "04")

    def test_actual_response_and_pii_removal(self) -> None:
        parsed = parse_response(ACTUAL_RESPONSE, "CJ대한통운", "04", "540885631633")

        self.assertEqual(parsed["status"], "complete")
        self.assertIsNone(parsed["error"])
        self.assertEqual(parsed["item_name"], "엑츠 베이킹소다 3L")
        self.assertEqual(len(parsed["events"]), 2)
        self.assertEqual(
            set(parsed["events"][0]),
            {"kind", "where", "timeString", "time", "level"},
        )
        serialized = repr(parsed)
        for pii in (
            "telno",
            "telno2",
            "manName",
            "manPic",
            "receiverName",
            "receiverAddr",
            "recipient",
            "senderName",
            "010-0000-0000",
            "받는 사람",
        ):
            self.assertNotIn(pii, serialized)

    def test_result_y_without_history(self) -> None:
        parsed = parse_response(
            {"result": "Y", "trackingDetails": []}, "CJ대한통운", "04", "1"
        )
        self.assertEqual(parsed["status"], "no_history")
        self.assertEqual(parsed["error"], "no_history")

    def test_result_n(self) -> None:
        parsed = parse_response(
            {"result": "N", "trackingDetails": []}, "CJ대한통운", "04", "1"
        )
        self.assertEqual(parsed["status"], "not_found")
        self.assertEqual(parsed["error"], "not_found")


if __name__ == "__main__":
    unittest.main()
