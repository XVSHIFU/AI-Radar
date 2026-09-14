import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx


def retry_after_seconds(error: Exception, now: datetime | None = None) -> int | None:
    """Honor server backoff; unknown 429s cool the source for fifteen minutes."""
    if not isinstance(error, httpx.HTTPStatusError):
        return None
    if error.response.status_code not in (429, 503):
        return None
    value = error.response.headers.get("Retry-After", "")
    default = 900 if error.response.status_code == 429 else 60
    try:
        seconds = float(value)
        if not math.isfinite(seconds):
            return default
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return default
            seconds = (date - (now or datetime.now(UTC))).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return default
    return max(default, math.ceil(seconds))
