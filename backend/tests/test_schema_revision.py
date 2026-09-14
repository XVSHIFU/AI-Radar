from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from radar.db_schema import SCHEMA_REVISION


def test_readiness_revision_matches_current_migration_head():
    root = Path(__file__).resolve().parents[1]
    config = Config()
    config.set_main_option("script_location", str(root / "alembic"))
    assert ScriptDirectory.from_config(config).get_current_head() == SCHEMA_REVISION
