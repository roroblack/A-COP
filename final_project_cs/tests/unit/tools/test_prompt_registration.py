from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.infrastructure.db.session import get_connection
from app.tools.read_tools import ALLOWED_PROMPT_KEYS, register_prompt_files


@pytest.fixture()
def database():
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            yield conn
    except Exception as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")


def _active_counts(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT prompt_key, count(*) FROM prompts WHERE prompt_key = ANY(%s) "
            "AND active=true GROUP BY prompt_key",
            (list(ALLOWED_PROMPT_KEYS),),
        )
        return dict(cur.fetchall())


def test_registers_four_prompts_idempotently(database):
    first, skipped = register_prompt_files(database)
    assert len(first) == 4
    assert len(first) == len(ALLOWED_PROMPT_KEYS)
    counts = _active_counts(database)
    assert set(counts) == ALLOWED_PROMPT_KEYS
    assert all(value == 1 for value in counts.values())

    with database.cursor() as cur:
        cur.execute("SELECT count(*) FROM prompts WHERE prompt_key = ANY(%s)", (list(ALLOWED_PROMPT_KEYS),))
        before = cur.fetchone()[0]
    second, skipped = register_prompt_files(database)
    with database.cursor() as cur:
        cur.execute("SELECT count(*) FROM prompts WHERE prompt_key = ANY(%s)", (list(ALLOWED_PROMPT_KEYS),))
        after = cur.fetchone()[0]
    assert len(second) == 4 and before == after
    assert all(value == 1 for value in _active_counts(database).values())


def test_disallowed_prompt_is_reported(database):
    root = Path("tests") / f".prompt_registration_{uuid4().hex}"
    path = root / "billing"
    path.mkdir(parents=True)
    unwanted = path / "answer.v1.md"
    try:
        unwanted.write_text("not deployable", encoding="utf-8")
        ids, skipped = register_prompt_files(database, str(root))
        assert ids == []
        assert str(unwanted) in skipped
    finally:
        unwanted.unlink(missing_ok=True)
        path.rmdir()
        root.rmdir()


def test_same_version_with_different_content_fails(database):
    root = Path("tests") / f".prompt_registration_{uuid4().hex}" / "order_shipping"
    root.mkdir(parents=True)
    path = root / "answer.v999.md"
    try:
        path.write_text("first", encoding="utf-8")
        register_prompt_files(database, str(root.parent))
        path.write_text("second", encoding="utf-8")
        with pytest.raises(ValueError, match="content differs"):
            register_prompt_files(database, str(root.parent))
    finally:
        path.unlink(missing_ok=True)
        root.rmdir()
        root.parent.rmdir()
        with database.transaction(), database.cursor() as cur:
            cur.execute("DELETE FROM prompts WHERE prompt_key='order_shipping.answer' AND version='999'")
