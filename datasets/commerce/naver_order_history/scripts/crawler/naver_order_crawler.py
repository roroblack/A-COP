#!/usr/bin/env python3
"""저장된 Chrome 프로필로 네이버페이 쇼핑 주문내역을 수집한다."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
    Locator,
    Page,
    Playwright,
    TimeoutError,
    sync_playwright,
)


LIST_URL = "https://pay.naver.com/pc/history?serviceChannel=SHOPPING&page={page}"
# 날짜 구간을 지정하면 기본 목록이 보여주지 않는 주문까지 조회된다.
# startDate/endDate는 YYYYMMDD 형식이며 실제로 서버가 인식하는 파라미터다.
LIST_URL_RANGED = LIST_URL + "&startDate={start}&endDate={end}"
DATE_RANGE: dict[str, str | None] = {"start": None, "end": None}


def split_date_ranges(
    start_date: str, end_date: str, split_months: int
) -> list[tuple[str, str]]:
    """날짜 범위를 달력 기준 N개월 단위의 구간으로 나눈다."""
    if split_months < 1:
        raise ValueError("분할 개월 수는 1 이상이어야 합니다.")

    start = datetime.strptime(start_date, "%Y%m%d").date()
    end = datetime.strptime(end_date, "%Y%m%d").date()
    if start > end:
        raise ValueError("조회 시작일은 종료일보다 늦을 수 없습니다.")

    ranges: list[tuple[str, str]] = []
    current = start
    while current <= end:
        month_index = current.year * 12 + current.month - 1 + split_months
        next_boundary = date(month_index // 12, month_index % 12 + 1, 1)
        current_end = min(end, next_boundary - timedelta(days=1))
        ranges.append((current.strftime("%Y%m%d"), current_end.strftime("%Y%m%d")))
        current = current_end + timedelta(days=1)
    return ranges


def list_url_for(page: int) -> str:
    """날짜 구간이 지정돼 있으면 구간을 포함한 목록 URL을 만든다."""
    if DATE_RANGE["start"] and DATE_RANGE["end"]:
        return LIST_URL_RANGED.format(
            page=page, start=DATE_RANGE["start"], end=DATE_RANGE["end"]
        )
    return LIST_URL.format(page=page)
ORDER_ID_PATTERN = re.compile(r"orders\.pay\.naver\.com/order/status/(\d+)")
AMOUNT_PATTERN = re.compile(r"[\d,]+")
QUANTITY_PATTERN = re.compile(r"수량\s*(\d+)개")
ORDERED_AT_PATTERN = re.compile(r"\d{4}\.\d{1,2}\.\d{1,2}\.\s*\d{1,2}:\d{2}:\d{2}")
CONFIRMED_AT_PATTERN = re.compile(r"구매확정일\s*(\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.\s*\([^)]+\))")
PAYMENT_DATE_PATTERN = re.compile(r"(\d{1,2}\.\s*\d{1,2}\.\s*\d{1,2}:\d{2})")

CARD_SELECTOR = 'li[class*="PaymentItem_item-payment"]'
STATUS_SELECTOR = '[class*="OrderStatus_value"]'
PRODUCT_NAME_SELECTOR = '[class*="ProductName_name"]'
PRICE_SELECTOR = '[class*="PaymentItem_price"]'
PAYMENT_TIME_SELECTOR = '[class*="PaymentItem_time"]'
DETAIL_LINK_SELECTOR = 'a[class*="PaymentItem_view-detail"]'
PRODUCT_LINK_SELECTOR = 'a[class*="PaymentItem_product-detail"]'

AUTH_ERROR_MESSAGE = (
    "네이버 로그인 페이지로 이동했습니다. 재시도하지 않고 즉시 중단합니다. "
    "naver_profile의 로그인 상태를 브라우저에서 직접 확인하세요."
)


class AuthenticationRequired(RuntimeError):
    """로그인 페이지 리다이렉트를 발견했음을 나타낸다."""


@dataclass
class CrawlStats:
    pages: int = 0
    cards: int = 0
    order_links: int = 0
    detail_success: int = 0
    detail_failure: int = 0
    new_orders: int = 0
    intervals: int = 0
    duplicates_skipped: int = 0


class CrawlLogger:
    """콘솔과 UTF-8 로그 파일에 같은 내용을 남긴다."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, *, error: bool = False) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        print(line, file=sys.stderr if error else sys.stdout, flush=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")


def check_authentication(page: Page) -> None:
    """nid.naver.com 리다이렉트면 즉시 중단한다."""
    if "nid.naver.com" in page.url.lower():
        raise AuthenticationRequired(AUTH_ERROR_MESSAGE)


def goto_checked(page: Page, url: str) -> None:
    """이동 성공 여부와 관계없이 로그인 리다이렉트를 먼저 확인한다."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    except Exception:
        check_authentication(page)
        raise
    check_authentication(page)


# 이동 전 대기 범위(초). --delay-min/--delay-max로 조정한다.
# 서버 부담을 줄이기 위한 값이므로 1초 아래로는 내리지 않는다.
DELAY_RANGE = [1.2, 3.0]
MIN_ALLOWED_DELAY = 1.0


def wait_before_navigation(logger: CrawlLogger, destination: str) -> float:
    """모든 페이지 이동 전에 지정된 범위만큼 기다린다."""
    seconds = random.uniform(DELAY_RANGE[0], DELAY_RANGE[1])
    logger.log(f"{destination} 이동 전 {seconds:.1f}초 대기")
    time.sleep(seconds)
    return seconds


# 화면 낭독용 라벨이 값 앞에 붙어 나오는 경우가 있어 제거한다.
# "수량"은 빼둔다. QUANTITY_PATTERN이 "수량 1개" 형태를 그대로 찾기 때문에
# 여기서 미리 떼어내면 매칭이 깨진다.
LABEL_PREFIXES = ("상품명", "주소", "판매자명", "결제일시", "주문번호")


def strip_label(value: str) -> str:
    """값 앞에 붙은 라벨 텍스트와 줄바꿈을 제거한다."""
    text = value.strip()
    for label in LABEL_PREFIXES:
        if text.startswith(label):
            remainder = text[len(label) :].lstrip(" \t\n:")
            if remainder:
                text = remainder
                break
    # 줄바꿈은 공백으로 합친다. 값이 여러 줄에 걸쳐 있어도 뒤쪽 정규식이 계속 동작한다.
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines) if lines else text


def first_text(scope: Page | Locator, selector: str) -> str | None:
    """첫 일치 요소의 정리된 텍스트를 반환한다."""
    try:
        locator = scope.locator(selector).first
        if locator.count() == 0:
            return None
        text = strip_label(locator.inner_text(timeout=2_000))
        return text or None
    except (TimeoutError, UnicodeError):
        return None


def first_href(scope: Locator, selector: str, base_url: str) -> str | None:
    try:
        locator = scope.locator(selector).first
        if locator.count() == 0:
            return None
        href = locator.get_attribute("href", timeout=2_000)
        return urljoin(base_url, href) if href else None
    except TimeoutError:
        return None


def locator_href(locator: Locator, base_url: str) -> str | None:
    """링크 요소 하나의 절대 URL을 반환한다."""
    try:
        href = locator.get_attribute("href", timeout=2_000)
        return urljoin(base_url, href) if href else None
    except TimeoutError:
        return None


def nearest_order_scope(card: Locator, detail_link: Locator) -> Locator:
    """상세 링크 하나에 대응하는 카드 내부 주문 영역을 찾는다."""
    scope = detail_link.locator("xpath=..")
    field_selector = ", ".join(
        (
            STATUS_SELECTOR,
            PRODUCT_NAME_SELECTOR,
            PRICE_SELECTOR,
            PAYMENT_TIME_SELECTOR,
            PRODUCT_LINK_SELECTOR,
        )
    )
    for _ in range(12):
        try:
            if (
                scope.locator(DETAIL_LINK_SELECTOR).count() == 1
                and scope.locator(field_selector).count() > 0
            ):
                return scope
            scope = scope.locator("xpath=..")
        except PlaywrightError:
            break
    return card


def scoped_text(scope: Locator, card: Locator, selector: str) -> str | None:
    """주문 영역 값을 우선 읽고 없으면 카드 공통값을 사용한다."""
    return first_text(scope, selector) or first_text(card, selector)


def scoped_href(
    scope: Locator, card: Locator, selector: str, base_url: str
) -> str | None:
    """주문 영역 링크를 우선 읽고 없으면 카드 공통 링크를 사용한다."""
    return first_href(scope, selector, base_url) or first_href(card, selector, base_url)


def parse_amount(value: str | None) -> int | None:
    """금액 문자열에서 숫자만 추출한다."""
    if not value:
        return None
    match = AMOUNT_PATTERN.search(value)
    return int(match.group(0).replace(",", "")) if match else None


def match_group(pattern: re.Pattern[str], value: str | None) -> str | None:
    if not value:
        return None
    match = pattern.search(value)
    return match.group(1).strip() if match else None


def normalize_product_url(value: str | None) -> str | None:
    """유입 추적 링크 안의 실제 상품 URL만 남긴다."""
    if not value:
        return None
    parsed = urlparse(value)
    target = parse_qs(parsed.query).get("retUrl", [None])[0]
    return target or value


def clean_seller_name(value: str | None) -> str | None:
    """접근성 라벨을 제외한 판매자명만 반환한다."""
    if not value:
        return None
    cleaned = re.sub(r"^판매자명\s*", "", value).strip()
    return cleaned or None


def empty_record() -> dict[str, Any]:
    """정규화 파이프라인이 기대하는 키를 빠짐없이 만든다."""
    return {
        "OrderId": None,
        "OrderedAt": None,
        "SellerName": None,
        "ProductName": None,
        "Quantity": None,
        "ProductPrice": None,
        "ShippingFee": None,
        "TotalAmount": None,
        "OrderStatus": None,
        "PurchaseConfirmedAt": None,
        "PaymentDate": None,
        "DeliveryRegion": None,
        "CourierCompany": None,
        "TrackingNumber": None,
        "DeliveryStatus": None,
        "DeliveryCompleteDate": None,
        "ProductUrl": None,
        "_detailFetched": False,
    }


def extract_list_record(
    card: Locator, detail_link: Locator, base_url: str
) -> tuple[dict[str, Any], str | None]:
    """카드 안의 상세 링크 하나에 대응하는 목록 필드를 추출한다."""
    record = empty_record()
    detail_url = locator_href(detail_link, base_url)
    order_match = ORDER_ID_PATTERN.search(detail_url or "")
    scope = nearest_order_scope(card, detail_link)
    product_price = parse_amount(scoped_text(scope, card, PRICE_SELECTOR))
    record.update(
        {
            "OrderId": order_match.group(1) if order_match else None,
            "ProductName": scoped_text(scope, card, PRODUCT_NAME_SELECTOR),
            "ProductPrice": product_price,
            "TotalAmount": product_price,
            "OrderStatus": scoped_text(scope, card, STATUS_SELECTOR),
            "PaymentDate": match_group(
                PAYMENT_DATE_PATTERN, scoped_text(scope, card, PAYMENT_TIME_SELECTOR)
            ),
            "ProductUrl": normalize_product_url(
                scoped_href(scope, card, PRODUCT_LINK_SELECTOR, base_url)
            ),
        }
    )
    return record, detail_url


def extract_summary_amount(page: Page, label: str) -> int | None:
    """결제정보의 라벨과 같은 행에서 금액을 가져온다."""
    for item_selector, label_selector, value_selector in (
        (
            '[class*="Summary_item-detail"]',
            '[class*="Summary_label"]',
            '[class*="Summary_area-value"]',
        ),
        (
            '[class*="SubSummary_item-detail"]',
            '[class*="SubSummary_label"]',
            '[class*="SubSummary_area-value"]',
        ),
    ):
        items = page.locator(item_selector)
        for index in range(items.count()):
            item = items.nth(index)
            if first_text(item, label_selector) == label:
                return parse_amount(first_text(item, value_selector))
    return None


def extract_delivery_region(page: Page) -> str | None:
    """상세주소 원문을 Python으로 가져오지 않고 시·구까지만 반환한다."""
    selector = '[class*="DeliveryContent_area-address"]'
    if page.locator(selector).count() == 0:
        return None
    return page.locator(selector).first.evaluate(
        """element => {
            const text = element.textContent || '';
            // 도 이름을 명시적으로 나열한다. [가-힣]+도 로 두면 앞에 붙은
            // '주소' 같은 라벨까지 함께 잡힌다.
            const match = text.match(
                /(서울특별시|부산광역시|대구광역시|인천광역시|광주광역시|대전광역시|울산광역시|세종특별자치시|제주특별자치도|경기도|강원특별자치도|강원도|충청북도|충청남도|전북특별자치도|전라북도|전라남도|경상북도|경상남도)\\s*([가-힣]+(?:시|군|구))/
            );
            return match ? `${match[1]} ${match[2]}` : null;
        }"""
    )


def extract_detail(context: BrowserContext, url: str) -> dict[str, Any]:
    """PII 선택자를 읽지 않고 상세 주문정보를 추출한다."""
    page = context.new_page()
    try:
        goto_checked(page, url)
        try:
            page.wait_for_selector('[class*="PaymentNumber_article"]', timeout=20_000)
        except TimeoutError:
            pass
        check_authentication(page)

        order_text = first_text(page, '[class*="PaymentNumber_article"]')
        option_text = first_text(page, '[class*="ProductDetail_option"]')
        delivery_text = first_text(page, '[class*="DeliveryState_article"]')
        seller_delivery_text = first_text(page, '[class*="ProductStore_delivery"]')

        quantity_text = option_text or first_text(page, '[class*="ProductDetail_article"]')
        quantity_match = QUANTITY_PATTERN.search(quantity_text or "")
        quantity_value = int(quantity_match.group(1)) if quantity_match else None
        if quantity_value is None:
            # 옵션이 있는 주문은 "수량" 라벨 없이 em 요소에 "1개"만 들어간다.
            # 옵션 문자열의 "12개입" 같은 값과 섞이지 않도록 전용 선택자를 쓴다.
            highlight = first_text(page, 'em[class*="ProductDetail_highlight"]')
            bare = re.search(r"(\d+)\s*개", highlight or "")
            if bare:
                quantity_value = int(bare.group(1))
        ordered_at_match = ORDERED_AT_PATTERN.search(order_text or "")
        confirmed_at = match_group(CONFIRMED_AT_PATTERN, delivery_text)

        total_amount = extract_summary_amount(page, "주문금액")
        product_amount = extract_summary_amount(page, "상품금액")
        shipping_fee = extract_summary_amount(page, "배송비")
        if shipping_fee is None:
            shipping_fee = parse_amount(seller_delivery_text)

        detail_status = first_text(page, '[class*="DeliveryState_state"]')
        detail_product = first_text(page, '[class*="ProductDetail_name"]')
        detail_price = parse_amount(first_text(page, '[class*="ProductDetail_price"]'))

        return {
            "OrderedAt": ordered_at_match.group(0) if ordered_at_match else None,
            "SellerName": clean_seller_name(
                first_text(page, '[class*="ProductStore_title"]')
            ),
            "ProductName": detail_product,
            "Quantity": quantity_value,
            "ProductPrice": product_amount if product_amount is not None else detail_price,
            "ShippingFee": shipping_fee,
            "TotalAmount": total_amount,
            "OrderStatus": detail_status,
            "PurchaseConfirmedAt": confirmed_at,
            "DeliveryRegion": extract_delivery_region(page),
            "DeliveryStatus": detail_status,
            "_detailFetched": True,
            **extract_tracking(page),
        }
    finally:
        page.close()


def extract_tracking(page: Page) -> dict[str, Any]:
    """'배송조회'를 눌러 택배사·송장번호·배송완료일시를 가져온다.

    배송조회 기간이 만료된 주문도 택배사와 송장번호는 남아 있다. 버튼이 없거나
    이동에 실패하면 조용히 빈 값을 돌려주고 전체 수집을 멈추지 않는다.
    """
    result: dict[str, Any] = {
        "CourierCompany": None,
        "TrackingNumber": None,
        "DeliveryCompleteDate": None,
    }
    try:
        button = page.locator("button:has-text('배송조회')")
        if button.count() == 0:
            return result
        button.first.click()
        page.wait_for_load_state("networkidle", timeout=20_000)
        page.wait_for_timeout(1200)
        if "tracking" not in page.url:
            return result
        check_authentication(page)

        result["CourierCompany"] = first_text(page, '[class*="Courier_company"]')
        number = first_text(page, '[class*="Courier_number"]')
        if number:
            digits = re.sub(r"\D", "", number)
            result["TrackingNumber"] = digits or None
        result["DeliveryCompleteDate"] = first_text(page, '[class*="DeliverySummary_date"]')
    except (TimeoutError, PlaywrightError):
        pass
    return result


def merge_detail(record: dict[str, Any], detail: dict[str, Any]) -> None:
    """상세값이 있을 때만 목록값을 덮어쓴다."""
    for key, value in detail.items():
        if value is not None or key == "_detailFetched":
            record[key] = value


def write_json_atomic(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def load_checkpoint(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"체크포인트 형식이 올바르지 않습니다: {path}")
    return value


def format_eta(seconds: float | None) -> str:
    if seconds is None:
        return "계산 중"
    if seconds < 60:
        return f"약 {seconds:.0f}초"
    return f"약 {seconds / 60:.1f}분"


def estimate_remaining(
    *,
    started_at: float,
    processed: int,
    index: int,
    cards_on_page: int,
    page_number: int,
    start_page: int,
    max_pages: int | None,
) -> float | None:
    if processed == 0:
        return None
    average = (time.monotonic() - started_at) / processed
    remaining = cards_on_page - index - 1
    if max_pages is not None:
        last_page = start_page + max_pages - 1
        remaining += max(0, last_page - page_number) * cards_on_page
    return average * remaining


def crawl(
    *,
    playwright: Playwright,
    profile_dir: Path,
    checkpoint_path: Path,
    logger: CrawlLogger,
    resume: bool,
    with_detail: bool,
    start_page: int,
    max_pages: int | None,
    date_ranges: list[tuple[str | None, str | None]],
) -> tuple[list[dict[str, Any]], CrawlStats, float]:
    if resume and checkpoint_path.exists():
        records = load_checkpoint(checkpoint_path)
        logger.log(f"체크포인트에서 {len(records)}건을 불러옴")
    else:
        records = []
        write_json_atomic(checkpoint_path, records)

    known_ids = {
        str(record["OrderId"])
        for record in records
        if record.get("OrderId") not in (None, "")
    }
    stats = CrawlStats()
    started_at = time.monotonic()
    # 프로필 디렉터리는 브라우저가 비정상 종료하면 쿠키를 잃는다. save_session.py가
    # 저장해 둔 storage_state 파일이 있으면 그것을 우선 사용한다.
    state_path = Path(__file__).resolve().parent / "naver_state.json"
    if state_path.exists():
        browser = playwright.chromium.launch(channel="chrome", headless=False)
        context = browser.new_context(storage_state=str(state_path))
    else:
        browser = None
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="chrome",
            headless=False,
        )

    try:
        page = context.pages[0] if context.pages else context.new_page()
        stats.intervals = len(date_ranges)

        for interval_index, (range_start, range_end) in enumerate(date_ranges, start=1):
            DATE_RANGE["start"] = range_start
            DATE_RANGE["end"] = range_end
            if range_start and range_end:
                interval_label = datetime.strptime(range_start, "%Y%m%d").strftime("%Y-%m")
                logger.log(
                    f"{interval_label} 구간 조회 중 "
                    f"({interval_index}/{stats.intervals}, {range_start}~{range_end})"
                )

            page_number = start_page
            last_page = start_page + max_pages - 1 if max_pages is not None else None
            while last_page is None or page_number <= last_page:
                list_url = list_url_for(page_number)
                wait_before_navigation(logger, f"목록 {page_number}페이지")
                goto_checked(page, list_url)
                try:
                    page.wait_for_selector(CARD_SELECTOR, timeout=20_000)
                except TimeoutError:
                    pass
                check_authentication(page)

                cards = page.locator(CARD_SELECTOR)
                card_count = cards.count()
                order_link_count = cards.locator(DETAIL_LINK_SELECTOR).count()
                stats.pages += 1
                stats.cards += card_count
                stats.order_links += order_link_count
                logger.log(
                    f"{page_number}페이지: 카드 {card_count}개, "
                    f"주문 링크 {order_link_count}개"
                )
                if card_count == 0:
                    logger.log(f"{page_number}페이지에 카드가 없어 순회를 종료함")
                    break

                page_new_orders = 0
                page_order_index = 0
                for index in range(card_count):
                    check_authentication(page)
                    card = cards.nth(index)
                    detail_links = card.locator(DETAIL_LINK_SELECTOR)
                    for link_index in range(detail_links.count()):
                        page_order_index += 1
                        try:
                            record, detail_url = extract_list_record(
                                card, detail_links.nth(link_index), page.url
                            )
                        except Exception as exc:
                            logger.log(
                                f"{page_number}페이지 {index + 1}번째 카드의 "
                                f"{link_index + 1}번째 주문 추출 실패, "
                                f"빈 값으로 계속함: {exc}",
                                error=True,
                            )
                            record, detail_url = empty_record(), None

                        order_id = record.get("OrderId")
                        if order_id and str(order_id) in known_ids:
                            stats.duplicates_skipped += 1
                            logger.log(f"이미 수집한 주문 건너뜀: {order_id}")
                            continue

                        if with_detail and detail_url:
                            wait_before_navigation(
                                logger, f"주문 {order_id or '번호 없음'} 상세"
                            )
                            try:
                                merge_detail(record, extract_detail(context, detail_url))
                                stats.detail_success += 1
                            except AuthenticationRequired:
                                raise
                            except Exception as exc:
                                stats.detail_failure += 1
                                logger.log(
                                    f"주문 {order_id or '번호 없음'} 상세 추출 실패, "
                                    f"목록값으로 계속함: {exc}",
                                    error=True,
                                )
                        elif with_detail:
                            stats.detail_failure += 1
                            logger.log("상세링크가 없어 목록값으로 계속함", error=True)

                        records.append(record)
                        if order_id:
                            known_ids.add(str(order_id))
                        stats.new_orders += 1
                        page_new_orders += 1
                        write_json_atomic(checkpoint_path, records)

                        eta = estimate_remaining(
                            started_at=started_at,
                            processed=stats.new_orders,
                            index=page_order_index - 1,
                            cards_on_page=order_link_count,
                            page_number=page_number,
                            start_page=start_page,
                            max_pages=max_pages,
                        )
                        eta_scope = "지정 범위" if max_pages is not None else "현재 페이지"
                        logger.log(
                            f"진행: 현재 페이지 {page_number}, 누적 {len(records)}건, "
                            f"{eta_scope} 예상 남은 시간 {format_eta(eta)}"
                        )

                if page_new_orders == 0:
                    logger.log("이전 페이지와 동일한 결과가 반환되어 순회를 종료함")
                    break
                page_number += 1
    finally:
        write_json_atomic(checkpoint_path, records)
        context.close()
        if browser is not None:
            browser.close()

    elapsed = time.monotonic() - started_at
    return records, stats, elapsed


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    detail_group = parser.add_mutually_exclusive_group()
    detail_group.add_argument(
        "--with-detail",
        dest="with_detail",
        action="store_true",
        help="상세 페이지도 수집함(기본값)",
    )
    detail_group.add_argument(
        "--no-detail",
        dest="with_detail",
        action="store_false",
        help="목록 카드의 필드만 수집함",
    )
    parser.set_defaults(with_detail=True)
    parser.add_argument("--start-page", type=int, default=1, help="시작 페이지(기본 1)")
    parser.add_argument("--max-pages", type=int, default=None, help="수집할 최대 페이지 수")
    parser.add_argument("--resume", action="store_true", help="체크포인트의 주문번호를 건너뜀")
    parser.add_argument(
        "--start-date",
        help="조회 시작일 YYYYMMDD. --end-date와 함께 쓰면 그 구간만 수집한다.",
    )
    parser.add_argument(
        "--end-date",
        help="조회 종료일 YYYYMMDD",
    )
    parser.add_argument(
        "--split-months",
        type=int,
        default=None,
        help="날짜 범위를 지정한 개월 수 단위로 분할함",
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=DELAY_RANGE[0],
        help=f"이동 전 최소 대기 초 (기본 {DELAY_RANGE[0]}, {MIN_ALLOWED_DELAY} 미만 불가)",
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=DELAY_RANGE[1],
        help=f"이동 전 최대 대기 초 (기본 {DELAY_RANGE[1]})",
    )
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=script_dir / "naver_profile",
        help="로그인 세션이 저장된 Chrome 프로필 경로",
    )
    args = parser.parse_args()
    if args.start_page < 1:
        parser.error("--start-page는 1 이상이어야 합니다.")
    if args.max_pages is not None and args.max_pages < 1:
        parser.error("--max-pages는 1 이상이어야 합니다.")
    if args.delay_min < MIN_ALLOWED_DELAY:
        parser.error(f"--delay-min은 {MIN_ALLOWED_DELAY} 이상이어야 합니다.")
    if args.delay_max < args.delay_min:
        parser.error("--delay-max는 --delay-min 이상이어야 합니다.")
    if bool(args.start_date) != bool(args.end_date):
        parser.error("--start-date와 --end-date는 함께 지정해야 합니다.")
    if args.split_months is not None and args.split_months < 1:
        parser.error("--split-months는 1 이상이어야 합니다.")
    if args.split_months is not None and not args.start_date:
        parser.error("--split-months는 날짜 범위와 함께 지정해야 합니다.")
    for value in (args.start_date, args.end_date):
        if value and not re.fullmatch(r"\d{8}", value):
            parser.error("날짜는 YYYYMMDD 형식이어야 합니다.")
    if args.start_date and args.end_date:
        try:
            split_date_ranges(args.start_date, args.end_date, args.split_months or 1)
        except ValueError as exc:
            parser.error(str(exc))
    DELAY_RANGE[0] = args.delay_min
    DELAY_RANGE[1] = args.delay_max
    DATE_RANGE["start"] = args.start_date
    DATE_RANGE["end"] = args.end_date
    return args


def configure_console() -> None:
    """Windows 콘솔에서 가능한 경우 UTF-8 출력을 사용한다."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    configure_console()
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    raw_dir = (script_dir / ".." / ".." / "raw").resolve()
    checkpoint_path = raw_dir / ".checkpoint.partial"
    logger = CrawlLogger(raw_dir / "_crawl_log.txt")
    logger.log("수집 시작")

    if args.start_date and args.end_date:
        if args.split_months is not None:
            date_ranges: list[tuple[str | None, str | None]] = split_date_ranges(
                args.start_date, args.end_date, args.split_months
            )
        else:
            date_ranges = [(args.start_date, args.end_date)]
    else:
        date_ranges = [(None, None)]

    try:
        with sync_playwright() as playwright:
            records, stats, elapsed = crawl(
                playwright=playwright,
                profile_dir=args.profile_dir.expanduser().resolve(),
                checkpoint_path=checkpoint_path,
                logger=logger,
                resume=args.resume,
                with_detail=args.with_detail,
                start_page=args.start_page,
                max_pages=args.max_pages,
                date_ranges=date_ranges,
            )
    except AuthenticationRequired:
        logger.log(AUTH_ERROR_MESSAGE, error=True)
        return 2
    except KeyboardInterrupt:
        logger.log("사용자 요청으로 중단함. 체크포인트는 보존됨", error=True)
        return 130
    except Exception as exc:
        logger.log(f"수집 중단. 체크포인트는 보존됨: {exc}", error=True)
        return 1

    output_path = raw_dir / f"{datetime.now():%Y-%m-%d}_{len(records)}건.json"
    write_json_atomic(output_path, records)
    average_per_interval = stats.new_orders / stats.intervals if stats.intervals else 0.0
    logger.log(
        f"완료 통계: 총 페이지 {stats.pages}, 총 카드 수 {stats.cards}, "
        f"총 주문 수 {len(records)}, 발견 주문 링크 {stats.order_links}, "
        f"상세 성공 {stats.detail_success}, 상세 실패 {stats.detail_failure}, "
        f"총 구간 {stats.intervals}, 구간당 평균 수집 {average_per_interval:.1f}건, "
        f"중복으로 건너뛴 건수 {stats.duplicates_skipped}, "
        f"소요 시간 {elapsed:.1f}초"
    )
    logger.log(f"저장 파일: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
