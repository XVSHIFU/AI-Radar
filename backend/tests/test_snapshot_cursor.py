from datetime import date
from uuid import uuid4

import pytest

from radar.cursor import decode_snapshot_cursor, encode_snapshot_cursor
from radar.repository import InvalidCursor
from radar.schemas import Filters


def test_snapshot_cursor_is_signed_and_bound_to_filters() -> None:
    snapshot_id = uuid4()
    filters = Filters(category="research", date_from=date(2026, 9, 1))
    cursor = encode_snapshot_cursor(snapshot_id, 25, filters, "a-long-development-secret")
    assert decode_snapshot_cursor(cursor, filters, "a-long-development-secret") == (snapshot_id, 25)
    with pytest.raises(InvalidCursor):
        decode_snapshot_cursor(cursor, Filters(category="product"), "a-long-development-secret")
