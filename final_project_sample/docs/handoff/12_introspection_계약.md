# Introspection contract v1

`app.introspection.snapshot()`(별칭 `describe`)이 basement 의 read-only
조립 상태 projection 이다. `GET /introspection`(scope `ops:introspect`)이 이걸
그대로 JSON 으로 낸다 — **외부 개발 콘솔**(`final_project_ui`)이 이 프로세스 안에서
파이썬을 실행하지 않고 붙는 유일한 통로다.

★2026-08-17: 예전에는 이 값을 `/ui/admin`(이 저장소 안의 HTML 화면)이 렌더링했다.
그 화면은 지웠다 — 개발 콘솔은 별도 프로그램으로 옮겨갔고, 그 프로그램은 read-only 라
이 프로세스를 직접 부를 수 없다(`final_project_ui/CLAUDE.md` §0.3). 그래서 데이터를
**HTTP 로** 낸다. `snapshot()` 자체는 그대로다 — 소비자만 HTML 렌더러에서 HTTP
핸들러로 바뀌었다.

## 반환 형태

- `contract_version`: `"1.0"`
- `config_revision`, `modules`(활성 모듈), `ports`(선언된 Port)
- `team_manifests`: `team_id`, `display_name`, `capabilities`, `allowed_tools`,
  `knowledge_scope`, `max_steps`, `active`, `revision`
- `teams`: 선언(`team_id`·`active`·`implementation_ref`) + 조립된 `manifest`
  (조립 실패 시 `manifest: null` — "없다" 와 "모른다" 를 구분한다)
- `port_implementations`: 실제 조립된 구현 클래스 이름. **하드코딩 맵으로
  추측하지 않는다** — 얻지 못하면 `null`
- `guardrails`: `config/guardrails.yaml` 값 그대로
- `llm`: `provider`, `model`, `api_key`(마스킹된 `"sk-****"` 또는 `"missing"` — 원문 없음)

## 경계

- JSON-safe 데이터만 담는다. Team 을 실행하지 않고, 쓰기를 하지 않고,
  API key 원문을 내지 않는다
- `GET /introspection` 은 `ops:introspect` scope 로 인증한다.
  `mcp:read` 와는 다른 scope 다 — 개인 AI 용 표면과 우리 도구용 표면을 가른다
- `/v1` 아래에 두지 않는다 — case 리소스가 아니라 `/health` 급의 운영 메타데이터다
