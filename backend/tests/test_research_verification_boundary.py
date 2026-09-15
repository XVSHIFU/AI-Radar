from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from radar.research_guard import ResearchRejected
from radar.research_verify import VerificationExecutor, verification_destination


async def test_operator_verification_only_releases_category_counts():
    execute = AsyncMock(
        return_value={
            "rows": [{"category": "model_release", "count": 5}],
            "scope_id": "private-scope",
            "data_revision": "internal-revision",
        }
    )
    executor = VerificationExecutor(SimpleNamespace(execute=execute))
    for name, arguments in [
        ("search_events", {}),
        ("get_event_evidence", {}),
        ("load_research_skill", {}),
        ("aggregate_events", {"dimension": "date"}),
    ]:
        with pytest.raises(ResearchRejected, match="TOOL_UNAVAILABLE"):
            await executor.execute(name, arguments)
    assert execute.await_count == 0
    result = await executor.execute("aggregate_events", {"dimension": "category"})
    assert result == {"rows": [{"category": "model_release", "count": 5}]}
    assert execute.await_count == 1


def test_operator_verification_rejects_changed_provider_configuration():
    approved = dict(
        llm_provider="deepseek", llm_base_url="https://api.deepseek.com", llm_model="deepseek-flash"
    )
    verification_destination(SimpleNamespace(**approved))
    for key, value in [
        ("llm_provider", "custom"),
        ("llm_base_url", "https://other.example"),
        ("llm_model", "another-model"),
    ]:
        with pytest.raises(ValueError, match="authorization"):
            verification_destination(SimpleNamespace(**{**approved, key: value}))
