# 15 — basement 버전·배포 계약

basement는 별도 pip 패키지나 자동 적용기가 아니라, 선언된 소스 파일과 그
파일의 해시를 함께 전달하는 export artifact다. 현재 artifact의
`basement_version`은 `0.2.0`이고 manifest 계약 버전은 `1.0`이다.

## 경계와 manifest

경계는 `scripts/basement_manifest.py`의 `BASEMENT_COMPONENTS` 선언이 소유한다.
현재 컴포넌트는 `app/core`, `app/domain`, `app/application`,
`app/infrastructure`, `app/presentation`이다. `__pycache__`, `*.pyc`,
`app/infrastructure/db/migrations/002_domain_*.sql`은 export하지 않는다.

manifest에는 basement 버전, source commit/tag, UTC 생성 시각, 컴포넌트와
제외 목록, 파일별 SHA-256, 계약 버전, export 도구 버전이 들어간다. 파일
경로는 저장소 상대 POSIX 경로로 기록하고 정렬한다.

## export 사용법

저장소 루트에서 실행한다.

```powershell
python -m scripts.export_basement
```

결과는 `dist/basement/manifest.json`과 `dist/basement/files/` 아래에 생성된다.
다른 위치를 검사하거나 테스트하려면 `--output-dir`를 사용할 수 있다.

cs 프로젝트에서는 `manifest.json`의 `files[].path`와 SHA-256을 먼저 확인한
뒤 `files/`의 파일을 basement 경계에 수동으로 diff·적용한다. 이 도구는 cs
프로젝트를 찾아가거나 파일을 자동 적용하지 않는다.

## 버전 규칙

SemVer 기준은 `docs/handoff/10_도메인_교체_가이드.md`의 경계를 따른다. 기존
계약과의 버그 수정은 patch, 호환 가능한 기능·Port·registry ID 추가는
minor, 필수 계약 필드·Port 인터페이스·registry ID 제거/변경은 major다.
`app/modules`, `config`, `knowledge`와 같은 복사본의 도메인 변경은 basement
버전과 별도로 관리한다.

export artifact는 빌드 산출물이므로 `dist/` 전체를 git에 커밋하지 않는다.
