from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from radar.models import LlmCallRow
from radar.qa_service import QaError, QaService

pytestmark = pytest.mark.postgres


class NeverClient:
    async def complete_json(self, *, system: str, user: str):
        raise AssertionError("provider must not be called by claim tests")


@pytest.mark.asyncio
async def test_answer_idempotency_is_persistent_and_payload_bound(postgres_database: Any) -> None:
    engine = create_async_engine(postgres_database.rendered_url, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    service = QaService(sessions, NeverClient())
    try:
        call_id = await service.claim("stable-key", "a" * 64)
        with pytest.raises(QaError) as replay:
            await service.claim("stable-key", "a" * 64)
        assert replay.value.code == "IDEMPOTENCY_REPLAY" and replay.value.status == 409
        with pytest.raises(QaError) as conflict:
            await service.claim("stable-key", "b" * 64)
        assert conflict.value.code == "IDEMPOTENCY_KEY_CONFLICT" and conflict.value.status == 409
        async with sessions() as session:
            rows = list(
                (
                    await session.scalars(
                        select(LlmCallRow).where(
                            LlmCallRow.logical_request_id == "answer:stable-key"
                        )
                    )
                ).all()
            )
        assert len(rows) == 1 and rows[0].id == call_id and rows[0].status == "pending"
    finally:
        await engine.dispose()
