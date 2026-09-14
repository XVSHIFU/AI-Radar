from datetime import date
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from radar.models import EventRow
from radar.postgres_repository import PostgresRepository
from radar.schemas import Category, Filters


def test_event_query_compiles_for_postgresql_with_required_order() -> None:
    statement = select(EventRow).order_by(
        EventRow.event_date.desc().nulls_last(), EventRow.id.desc()
    )
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "NULLS LAST" in sql
    assert "events.id DESC" in sql


@pytest.mark.asyncio
async def test_insights_uses_filtered_database_aggregates_in_one_snapshot() -> None:
    class Result:
        def __init__(self, rows: list[tuple[object, int]]):
            self.rows = rows

        def all(self) -> list[tuple[object, int]]:
            return self.rows

    class Context:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *_args: object) -> None:
            return None

    class Session:
        def __init__(self) -> None:
            self.statements: list[Any] = []
            self.results = [
                Result([]),
                Result([(date(2026, 9, 8), 2)]),
                Result([("research", 2)]),
            ]

        async def __aenter__(self) -> "Session":
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def begin(self) -> Context:
            return Context()

        async def scalar(self, statement: Any) -> int:
            self.statements.append(statement)
            return 2

        async def execute(self, statement: Any) -> Result:
            self.statements.append(statement)
            return self.results.pop(0)

    session = Session()
    repository = PostgresRepository(lambda: session, "secret-secret-secret")
    snapshot = await repository.insight_summary(
        Filters(
            q="DeepSeek",
            category=Category.RESEARCH,
            date_from=date(2026, 9, 8),
            date_to=date(2026, 9, 10),
            min_importance=4,
        )
    )

    assert str(session.statements[0]) == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    sql = [
        str(
            statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        for statement in session.statements[1:]
    ]
    assert len(sql) == 3
    assert all("events.status = 'published'" in statement for statement in sql)
    assert all("events.category = 'research'" in statement for statement in sql)
    assert all("events.date_precision = 'day'" in statement for statement in sql)
    assert all("events.event_date >= '2026-09-08'" in statement for statement in sql)
    assert all("events.event_date <= '2026-09-10'" in statement for statement in sql)
    assert all("events.importance >= 4" in statement for statement in sql)
    assert all("deepseek" in statement.lower() for statement in sql)
    assert "GROUP BY events.event_date" in sql[1]
    assert "GROUP BY events.category" in sql[2]
    assert all(" LIMIT " not in statement.upper() for statement in sql)
    assert snapshot.total_events == 2
    assert snapshot.daily == {date(2026, 9, 8): 2}
    assert snapshot.categories == {Category.RESEARCH: 2}
