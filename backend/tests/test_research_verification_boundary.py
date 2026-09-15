from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from radar.research_guard import ResearchRejected
from radar.research_verify import VerificationExecutor


async def test_operator_verification_only_releases_category_counts():
    execute = AsyncMock(return_value={"rows": [{"category": "model_release", "count": 5}]})
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
    assert result["rows"][0]["count"] == 5 and execute.await_count == 1
