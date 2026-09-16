import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


quality = load("research_quality")
with patch.dict(sys.modules, {"research_quality": quality}):
    seed = load("research_quality_seed")
CORPUS = json.loads(quality.CORPUS.read_text(encoding="utf-8"))
DATABASE = "radar_test_" + "a" * 32


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:private@127.0.0.1/ai_radar",
        "postgresql://user:private@192.168.194.129/" + DATABASE,
        "postgresql://user:private@localhost/radar_test_backup",
        "postgresql://user:private@localhost/" + DATABASE + "?host=remote",
        "sqlite:///" + DATABASE,
        "private-not-a-url",
    ],
)
async def test_unsafe_target_rejected_before_connect_without_echoing_secrets(url):
    with patch.object(seed.asyncpg, "connect", new_callable=AsyncMock) as connect:
        with pytest.raises(ValueError) as failure:
            await seed.install(url, CORPUS)
        assert "private" not in str(failure.value)
        connect.assert_not_awaited()


def test_plan_links_all_frozen_evidence_and_keeps_sources_disabled():
    batches = seed.seed_batches(CORPUS)
    assert len(batches["events"]) == 12
    assert len(batches["evidence"]) == len(batches["articles"]) == 14
    event_ids = {row[0] for row in batches["events"]}
    version_ids = {row[0] for row in batches["article_versions"]}
    assert all(row[1] in event_ids and row[2] in version_ids for row in batches["evidence"])
    assert "false" in seed.INSERTS["sources"]
    assert sum(row[2] == "orion" for row in batches["entity_aliases"]) == 2
    assert all(row[-2] for row in batches["events"])


class Transaction:
    def __init__(self):
        self.exit_exception = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.exit_exception = exc_type


class Connection:
    def __init__(self, *, actual=DATABASE, occupied=False, fail_write=False):
        self.actual, self.occupied = actual, occupied
        self.tx = Transaction()
        self.execute = AsyncMock()
        self.executemany = AsyncMock(
            side_effect=RuntimeError("fixture write failure") if fail_write else None
        )

    def transaction(self):
        return self.tx

    async def fetchval(self, statement):
        if "current_database" in statement:
            return self.actual
        if "alembic_version" in statement:
            return "0013_public_quota_retention"
        return self.occupied


async def test_actual_connection_identity_is_rechecked_before_any_write():
    connection = Connection(actual="ai_radar")
    with pytest.raises(ValueError, match="does not match"):
        await seed.seed(connection, DATABASE, CORPUS)
    connection.execute.assert_not_awaited()
    connection.executemany.assert_not_awaited()


async def test_nonempty_database_is_never_cleared_or_overwritten():
    connection = Connection(occupied=True)
    with pytest.raises(ValueError, match="not empty"):
        await seed.seed(connection, DATABASE, CORPUS)
    connection.executemany.assert_not_awaited()
    assert connection.tx.exit_exception is ValueError
    assert not any(
        "DELETE" in call.args[0] or "TRUNCATE" in call.args[0]
        for call in connection.execute.await_args_list
    )


async def test_seed_write_failure_exits_transaction_for_rollback():
    connection = Connection(fail_write=True)
    with pytest.raises(RuntimeError, match="fixture write failure"):
        await seed.seed(connection, DATABASE, CORPUS)
    assert connection.tx.exit_exception is RuntimeError
    assert connection.executemany.await_count == 1


async def test_plan_success_reports_counts_without_credentials():
    connection = Connection()
    result = await seed.seed(connection, DATABASE, CORPUS)
    assert result["counts"]["evidence"] == 14
    assert connection.executemany.await_count == 9
    assert connection.tx.exit_exception is None
