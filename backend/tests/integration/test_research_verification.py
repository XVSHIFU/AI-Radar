from uuid import uuid4

import pytest
from sqlalchemy import select
from test_public_quota import ledger  # noqa: F401

from radar.config import Settings
from radar.deepseek_client import ProviderUsage
from radar.models import LlmCallRow
from radar.research_guard import ModelLease, ResearchRejected
from radar.research_verify import VerificationLedger

pytestmark = pytest.mark.postgres


async def test_verification_replay_is_blocked_and_usage_is_separate_from_public_quota(ledger):  # noqa: F811
    run_id = uuid4()
    probe = VerificationLedger(ledger.sessions, run_id, Settings())
    lease = ModelLease(1, 1000, 512)
    await probe.claim(run_id, lease)
    restarted = VerificationLedger(ledger.sessions, run_id, Settings())
    with pytest.raises(ResearchRejected, match="IDEMPOTENCY_REPLAY"):
        await restarted.claim(run_id, lease)
    await probe.settle(run_id, lease, ProviderUsage(50, 10, 60), "completed")
    async with ledger.sessions() as session:
        row = await session.scalar(
            select(LlmCallRow).where(LlmCallRow.logical_request_id == probe.key(1))
        )
        assert row.purpose == "admin_test" and row.status == "completed"
        assert (row.prompt_tokens, row.completion_tokens) == (50, 10)
    with pytest.raises(ResearchRejected, match="RUN_NOT_FOUND"):
        await probe.settle(uuid4(), lease, None, "failed")
    await probe.settle(run_id, lease, None, "failed")
    assert len(probe.usage) == 1
