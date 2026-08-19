"""Apply all SQL migrations, safely repeatable.

★basement 는 자기 core 마이그레이션(`001_schema.sql` 등)만 갖는다. 도메인
  마이그레이션(예: `002_domain_customer_ops.sql`)은 domain-owned 이므로
  `config/migrations/`(product 쪽, `docs/handoff/10` §0 경계표)에 둔다 —
  basement 패키지 안에 도메인 SQL 을 물리적으로 넣지 않는다. 파일명
  순서(001, 002, ...)로 정렬해 함께 적용한다.
"""
from pathlib import Path

from acop_basement.infrastructure.db.session import get_connection

CORE_MIGRATIONS_DIR = Path(__file__).with_name("migrations")
DOMAIN_MIGRATIONS_DIR = Path("config") / "migrations"


def main() -> None:
    files = sorted(
        [*CORE_MIGRATIONS_DIR.glob("*.sql"), *DOMAIN_MIGRATIONS_DIR.glob("*.sql")],
        key=lambda p: p.name,
    )
    sql = "\n".join(p.read_text(encoding="utf-8") for p in files)
    with get_connection() as conn:
        with conn.transaction():
            conn.execute(sql)
    print(f"Applied {len(files)} migrations from {CORE_MIGRATIONS_DIR} and {DOMAIN_MIGRATIONS_DIR}")


if __name__ == "__main__":
    main()
