from datetime import UTC, datetime

import pytest

from radar.ingest.dates import published_datetime


@pytest.mark.parametrize(
    "value",
    [
        "Mon, 14 Sep 2026 08:00:00 +0800",
        "2026-09-14T00:00:00Z",
        "2026-09-14T08:00:00+08:00",
    ],
)
def test_preserves_publication_instant(value):
    assert published_datetime(value) == datetime(2026, 9, 14, tzinfo=UTC)


@pytest.mark.parametrize("value", [None, "", "garbage", "2026-09-14", "2026-09-14T08:00:00"])
def test_ambiguous_dates_remain_unknown(value):
    assert published_datetime(value) is None
