from sqlalchemy.engine import make_url

from radar.config import Settings


def test_alembic_url_preserves_special_character_password() -> None:
    password = "p@ss:%/word?#[]"
    settings = Settings(
        _env_file=None,
        db_host="127.0.0.1",
        db_port=55432,
        db_name="radar_test_config",
        db_user="radar",
        db_password=password,
    )

    rendered = settings.alembic_url()

    assert rendered is not None
    assert "***" not in rendered
    assert make_url(rendered).password == password
    assert make_url(rendered).database == "radar_test_config"
