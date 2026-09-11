from sqlalchemy.dialects import postgresql

from radar.register_sources import CURATED_SOURCE_CANDIDATES, source_upserts


def test_source_catalog_matches_five_validated_candidates() -> None:
    assert [(item.name, item.feed_url) for item in CURATED_SOURCE_CANDIDATES] == [
        ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
        ("arXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI"),
        ("Google Research", "https://research.google/blog/rss/"),
        ("AWS Machine Learning", "https://aws.amazon.com/blogs/machine-learning/feed/"),
        ("NVIDIA Technical Blog", "https://developer.nvidia.com/blog/feed/"),
    ]


def test_source_upserts_default_to_disabled_unverified() -> None:
    statements = source_upserts(False)
    assert len(statements) == 5
    for statement in statements:
        compiled = statement.compile(dialect=postgresql.dialect())
        sql = str(compiled)
        values = list(compiled.params.values())
        assert "ON CONFLICT (name) DO UPDATE" in sql
        assert False in values
        assert "unverified" in values


def test_enable_requires_explicit_true_input() -> None:
    for statement in source_upserts(True):
        assert True in statement.compile(dialect=postgresql.dialect()).params.values()
