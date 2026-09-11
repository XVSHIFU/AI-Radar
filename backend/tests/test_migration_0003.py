import runpy
from pathlib import Path
from typing import Any

from alembic import op


def test_0003_backfills_terminal_mixed_job_run(monkeypatch) -> None:
    statements: list[str] = []
    monkeypatch.setattr(op, "execute", lambda sql: statements.append(str(sql)))
    for name in (
        "add_column",
        "alter_column",
        "create_unique_constraint",
        "create_table",
    ):
        monkeypatch.setattr(op, name, lambda *_args, **_kwargs: None)

    migration = runpy.run_path(
        str(Path(__file__).parents[1] / "alembic" / "versions" / "0003_persistent_article_jobs.py")
    )
    upgrade: Any = migration["upgrade"]
    upgrade()

    sql = "\n".join(statements)
    assert "SET stage = 'feed_discovery' WHERE stage = 'rss_fetch'" in sql
    assert "jobs.active_jobs = 0" in sql
    assert "jobs.failed_jobs > 0 AND jobs.succeeded_jobs > 0 THEN 'partial'" in sql
    assert "WHEN jobs.failed_jobs > 0 THEN 'failed'" in sql
    assert "ELSE 'success'" in sql
    assert "finished_at = COALESCE(run.finished_at, now())" in sql
    assert "failed_jobs = jobs.failed_jobs" in sql
