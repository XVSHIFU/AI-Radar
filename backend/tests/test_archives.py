from datetime import date

from radar.ingest.archives import (
    arxiv_query,
    entry_day,
    in_range,
    parse_anthropic_archive,
    parse_aws_archive,
    parse_deepseek_archive,
)
from radar.ingest.core import FeedEntry


def test_date_window_is_inclusive_and_uses_shanghai():
    entry = FeedEntry("title", "https://example.org", "https://example.org", "2026-07-31T16:00:00Z")
    assert entry_day(entry) == date(2026, 8, 1)
    assert in_range(entry, date(2026, 8, 1), date(2026, 9, 15))
    assert entry_day(FeedEntry("", "", "", "2026-08-01")) == date(2026, 8, 1)
    assert entry_day(FeedEntry("", "", "", "2026-08-01T12:00:00")) is None


def test_aws_pairs_each_heading_with_its_own_publication():
    html = (
        b'<h2 class="blog-post-title"><a href="/blogs/machine-learning/a/">A</a>'
        b'</h2><time datetime="2026-08-01T00:00:00Z">date</time><h2 class="blog-'
        b'post-title"><a href="/blogs/machine-learning/b/">B</a></h2><time datet'
        b'ime="2026-08-02T00:00:00Z">date</time>'
    )
    rows = parse_aws_archive(html)
    assert [x.title for x in rows] == ["A", "B"]
    assert [x.published for x in rows] == ["2026-08-01T00:00:00Z", "2026-08-02T00:00:00Z"]


def test_anthropic_uses_published_field_not_updated_field():
    html = (
        b'<a href="/news/model"><span class="Card__title">Model</span></a><scrip'
        b't>{"publishedOn":"2026-08-02T12:00:00Z","slug":{"current":"model"},"_u'
        b'pdatedAt":"2026-09-10T00:00:00Z"}</script>'
    )
    rows = parse_anthropic_archive(html)
    assert len(rows) == 1
    assert rows[0].published == "2026-08-02T12:00:00Z"


def test_deepseek_requires_matching_explicit_changelog_date():
    html = (
        b'<h2>Date: 2026-09-10</h2><a href="/news/news260910">news</a><a href="/'
        b'news/news260901">no matching date</a>'
    )
    rows = parse_deepseek_archive(html)
    assert len(rows) == 1 and rows[0].published == "2026-09-10"


def test_arxiv_query_preserves_local_date_edges():
    url = arxiv_query(date(2026, 8, 1), date(2026, 9, 15), 200)
    assert "202607311600" in url and "202609151559" in url
    assert "start=200" in url and "cat%3Acs.AI" in url
