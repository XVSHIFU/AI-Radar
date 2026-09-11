from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from radar.models import EventRow


def test_event_query_compiles_for_postgresql_with_required_order() -> None:
    statement = select(EventRow).order_by(
        EventRow.event_date.desc().nulls_last(), EventRow.id.desc()
    )
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "NULLS LAST" in sql
    assert "events.id DESC" in sql
