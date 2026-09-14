from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


def published_datetime(value: str | None) -> datetime | None:
    """Preserve explicit source time zones; never invent one for ambiguous dates."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)
