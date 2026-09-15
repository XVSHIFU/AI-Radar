from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from radar.postgres_repository import PostgresRepository
from radar.repository import EvidenceInvalid


class ScalarRows:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def scalars(self, statement: object) -> ScalarRows:
        return ScalarRows(self.rows)

    async def get(self, model: object, identity: object) -> None:
        return None


class FakeSessions:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def __call__(self) -> FakeSession:
        return FakeSession(self.rows)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "paragraphs,quote", [({}, "claim"), ({"p-1": "other"}, "claim"), ({"p-1": "claim"}, "")]
)
async def test_evidence_for_rejects_unlocatable_orm_rows(
    paragraphs: dict[str, str], quote: str
) -> None:
    event_id = UUID("20000000-0000-4000-8000-000000000001")
    version_id = UUID("30000000-0000-4000-8000-000000000001")
    row = SimpleNamespace(
        id=UUID("40000000-0000-4000-8000-000000000001"),
        event_id=event_id,
        article_version_id=version_id,
        paragraph_id="p-1",
        quote_text=quote,
        verification_status="verified",
        article_version=SimpleNamespace(
            paragraphs=paragraphs,
            source_url="https://example.com/a",
            title="Frozen",
            published_at=datetime(2026, 9, 12, tzinfo=UTC),
        ),
        event=SimpleNamespace(event_date=date(2026, 9, 12)),
    )
    repository = PostgresRepository(FakeSessions([row]), "review-secret-secret")  # type: ignore[arg-type]
    with pytest.raises(EvidenceInvalid):
        await repository.evidence_for(event_id)
