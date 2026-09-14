from datetime import UTC, datetime

import httpx
import pytest

from radar.ingest.throttle import retry_after_seconds


def failure(status, value=None):
    headers = {} if value is None else {"Retry-After": value}
    response = httpx.Response(
        status, headers=headers, request=httpx.Request("GET", "https://example.org")
    )
    return httpx.HTTPStatusError("limited", request=response.request, response=response)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 900),
        ("3600", 3600),
        ("1", 900),
        ("bad", 900),
        ("inf", 900),
        ("-10", 900),
    ],
)
def test_rate_limit_respects_delay_and_conservative_default(value, expected):
    assert retry_after_seconds(failure(429, value)) == expected


def test_retry_after_http_date_and_other_failures():
    now = datetime(2026, 9, 14, tzinfo=UTC)
    assert retry_after_seconds(failure(429, "Mon, 14 Sep 2026 01:00:00 GMT"), now) == 3600
    assert retry_after_seconds(failure(503, "120")) == 120
    assert retry_after_seconds(failure(404)) is None
    assert retry_after_seconds(httpx.ReadTimeout("timeout")) is None
