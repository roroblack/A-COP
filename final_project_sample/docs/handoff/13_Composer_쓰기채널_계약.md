# Composer 쓰기 채널 계약 v1

`app.application.composer_service`(`read_current` / `validate_candidate` /
`apply_candidate`)가 `config/project.yaml`(또는 주입된 대체 경로)을 검증·저장하는
**유일한** 통로다. `GET /composer/current`, `POST /composer/validate`,
`POST /composer/apply`(모두 scope `composer:write`)가 이걸 그대로 HTTP 로 낸다.

★왜 필요한가 — `/ui/composer` HTML 폼은 `composer_ui` 모듈로 끌 수 있다(릴리스 시
끈다, [[12_introspection_계약]] 이 설명하는 것과 같은 이유로 개발자 전용 화면이다).
그런데 Composer 는 basement 에 남는 **유일한 쓰기 기능**이다 — `final_project_ui`
는 read-only 원칙을 지키므로 이 저장소 파일을 직접 못 쓴다. 릴리스 이후에도
외부 콘솔이 모듈을 켜고 끄려면 HTML 페이지와 무관하게 사는 쓰기 채널이 있어야
한다. 이 세 엔드포인트는 **`composer_ui` 토글과 무관하게 항상 등록된다** —
scope 로만 잠근다.

Codex 교차검증(`docs/reports/2026-08-17_S-COMPOSER-WRITE-CHANNEL_검토.md`)이
설계를 검토했고, 그 리뷰가 잡은 세 결함(고정 임시 파일명 충돌, revision 확인 누락,
비원자적 교체)은 `composer_service.py` 에서 고쳤다. HTML 폼도 이제 자기 파일
I/O 를 갖지 않고 같은 `apply_candidate()` 를 부른다 — 검증·저장 정책이 한 곳에만
있다.

## 엔드포인트

### `GET /composer/current`
지금 파일의 `revision` 과 `config`(선언 전체, `revision` 필드 제외)를 낸다.
`apply` 를 보내기 전 `base_revision` 을 여기서 얻는다.

### `POST /composer/validate`
```json
{"config": {...}}
```
후보 선언을 **canonical loader**(`load_project_config`)로 검증만 한다.
**파일을 바꾸지 않는다.** 활성 Team 의 `implementation_ref` 를 실제로
import 해서 검증한다 — 이건 **이미 그 서버 프로세스에 설치된** 모듈만
로드할 수 있다. 원격에서 새 코드를 주입하는 경로가 아니다: 임의 문자열을
보내도 `importlib.import_module` 이 없는 모듈이면 그냥 실패한다.

응답: `{"valid": true, "errors": [], "revision": "..."}` 또는
`{"valid": false, "errors": ["..."]}`.

### `POST /composer/apply`
```json
{"config": {...}, "base_revision": "..."}
```
검증을 통과하고 `base_revision` 이 **지금 파일의 revision 과 일치할 때만**
원자적으로 쓴다.

- **revision 불일치 → `409 revision_conflict`**(`current_revision` 포함).
  400 이 아니다 — 요청 자체는 유효했고, 그 사이 파일이 바뀐 것이다.
  "마지막에 쓴 사람이 이긴다" 를 막는다.
- **검증 실패 → `422 invalid_declaration`**.
- 쓰기는 프로세스 내 lock(`_WRITE_LOCK`) 아래서, 임시 파일에 전부 쓴 뒤
  `os.replace()` 로 교체한다 — 쓰다가 죽어도 원본이 반쪽 상태로 남지 않는다.
  임시 파일명은 요청마다 `uuid4()` 를 섞는다 — 동시 요청이 서로의 후보를
  덮어쓰지 않는다.
- 성공 시 이전 파일을 `.yaml.bak` 으로 백업하고 새 `revision` 을 낸다.

## 경계 / 아직 없는 것

- **단일 프로세스 잠금**이다. 여러 워커·여러 인스턴스에 걸친 잠금은 없다 —
  지금은 로컬 단일 개발자 도구다. 인스턴스 레지스트리가 생기면 파일 lock 이나
  DB 조건부 쓰기로 넓혀야 한다(Codex 리뷰 §4 후속 과제).
- **CSRF/CORS**는 HTML 폼 경로에만 해당하고 이 API 자체는 다루지 않는다 —
  Bearer 토큰 인증이라 브라우저 쿠키 기반 CSRF 는 적용되지 않지만, 브라우저에서
  직접 호출하게 하려면 CORS 정책을 별도로 정해야 한다(아직 안 함).
- **audit 영속 로그는 없다.** 누가 언제 무엇을 apply 했는지는 지금 `.yaml.bak`
  하나만 남는다 — 이력 조회가 필요해지면 별도로 만든다.
- scope 는 `composer:write` 하나다. 읽기(`current`)·검증(`validate`)·적용(`apply`)
  을 더 세분화(`composer:read`/`composer:validate`/`composer:write`)하지 않았다 —
  지금 소비자가 셋 다 같은 신뢰 경계(외부 콘솔 운영자)에 있어서 나눌 이유가
  아직 없다.

## 테스트

`tests/e2e/test_composer_write_channel.py` — 인증 필요, scope 분리,
**`composer_ui` 가 꺼져 있어도 이 API 는 산다**(핵심 검사), validate 는 파일을
안 건드린다, 구현 안 된 `implementation_ref` 는 422 로 거부한다, 동일
`base_revision` 으로 보낸 동시 apply 2건은 1건만 200 이고 나머지는
409(`revision_conflict`).
