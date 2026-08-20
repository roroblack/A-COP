# 크롤러 코드 보관 위치

사용자가 이미 만든 네이버 주문내역 크롤러 코드를 이 폴더에서 관리한다. `naver_order_crawler.py` 같은 이름을 사용할 수 있으며 실제 파일명은 사용자가 정하면 된다.

이 폴더는 크롤러 코드와 출력 규약을 제공한다. 크롤러는 로그인하지 않는다. 사용자가 수동으로 로그인한 별도 브라우저 프로필을 Playwright가 재사용한다.

## 사전 준비

Python 패키지와 Playwright용 Chromium을 설치한다.

```bash
pip install -r requirements.txt
playwright install chromium
```

일상적으로 사용하는 Chrome 프로필과 분리된 디렉터리를 준비한다. 다음 예시는 현재 폴더 아래에 `naver_profile`을 만든다.

Windows에서 Chrome 실행 파일 경로는 설치 환경에 맞게 바꾼다.

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="./naver_profile"
```

macOS나 Linux에서는 다음과 같이 실행할 수 있다.

```bash
chrome --user-data-dir=./naver_profile
```

열린 브라우저에서 네이버에 직접 로그인한다. 로그인이 끝나면 Chrome을 완전히 닫는다. 같은 프로필을 Chrome과 크롤러에서 동시에 열지 않는다.

아이디나 비밀번호를 스크립트, 환경변수, `.env` 파일에 넣지 않는다.

## 실행 방법

```bash
python naver_order_crawler.py --profile-dir ./naver_profile
```

중단된 수집을 이어갈 때는 `--resume`을 추가한다.

```bash
python naver_order_crawler.py --profile-dir ./naver_profile --resume
```

시험할 때는 `--max-pages 1`처럼 페이지 수를 제한할 수 있다.

상세 조회와 페이지 이동 사이마다 2~6초의 무작위 대기시간이 있다. 주문이 많으면 수집에 오래 걸릴 수 있다. 진행 로그에 현재 페이지의 남은 예상 시간이 표시된다.

## 로그인 만료와 보안문자

로그인 페이지나 CAPTCHA 화면이 감지되면 스크립트는 즉시 멈춘다. 브라우저 창에서 직접 로그인하거나 보안문자를 확인한 뒤 `--resume`으로 다시 실행한다.

로그인이나 CAPTCHA를 자동으로 처리하는 기능은 계정 보호를 위해 의도적으로 넣지 않았다.

## 선택자 조정

네이버 페이지 구조는 바뀔 수 있다. 첫 실행 전 `naver_order_crawler.py` 상단의 `SELECTORS` 딕셔너리를 실제 페이지 개발자 도구에서 확인한다. 주문 목록, 상세 링크, 다음 페이지 버튼, 각 필드 선택자가 맞지 않으면 해당 값만 수정한다.

## 출력 위치

크롤러가 만든 raw 결과물은 `../../raw/`에 저장한다. 그러면 `../normalize.py`가 결과물을 바로 읽어 `../../processed/orders.jsonl`로 정규화할 수 있다.

raw 출력 파일은 `raw/YYYY-MM-DD_<n>건.json` 형태로 날짜별로 저장한다. 수집 중에는 `raw/.naver_order_checkpoint.partial`을 주문마다 갱신한다. `.partial` 파일은 `normalize.py`의 입력 대상이 아니다.

## raw 입력 형식

각 주문 객체는 다음 키 이름을 사용해야 한다.

```json
{
  "DeliveryStatus": "배송완료",
  "DeliveryCompleteDate": "8월 5일 (수) 17:40",
  "ProductName": "상품명, 3개",
  "PaymentDate": "8.2. 00:36",
  "DeliveryLocation": "배송 지역",
  "DeliveryLocationStatus": "배송완료",
  "DeliveryLocationDate": "08.05.(수) 17:40",
  "CourierCompany": "택배사",
  "TrackingNumber": "운송장번호"
}
```

`DeliveryStatus`, `DeliveryCompleteDate`, `ProductName`, `PaymentDate`, `DeliveryLocation`, `DeliveryLocationStatus`, `DeliveryLocationDate`, `CourierCompany`, `TrackingNumber`를 이 형식으로 출력하면 정규화 파이프라인이 이어진다.

크롤러가 결제금액, 판매자명, 주문번호도 수집할 수 있다면 함께 출력하는 편이 좋다. 이 값들이 있으면 `normalize.py`가 금액과 판매자 정보를 채우고 주문 식별자를 더 정확하게 만들 수 있다.

## 자격증명 주의사항

로그인 자격증명을 코드에 하드코딩하지 않는다. 크롤러는 기존 프로필의 로그인 상태만 재사용한다.
