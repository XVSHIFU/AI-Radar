import base64
import hashlib
import hmac
import json
from datetime import date
from uuid import UUID

from .repository import InvalidCursor
from .schemas import Filters


def _fingerprint(filters: Filters) -> str:
    raw = filters.model_dump_json(exclude_none=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def encode_cursor(event_date: date | None, event_id: UUID, filters: Filters, secret: str) -> str:
    payload = {
        "d": event_date.isoformat() if event_date else None,
        "id": str(event_id),
        "f": _fingerprint(filters),
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(body + signature).decode().rstrip("=")


def decode_cursor(value: str, filters: Filters, secret: str) -> tuple[date | None, UUID]:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        body, supplied = raw[:-32], raw[-32:]
        expected = hmac.new(secret.encode(), body, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            raise InvalidCursor("cursor signature is invalid")
        payload = json.loads(body)
        if payload["f"] != _fingerprint(filters):
            raise InvalidCursor("cursor does not belong to these filters")
        return (date.fromisoformat(payload["d"]) if payload["d"] else None, UUID(payload["id"]))
    except InvalidCursor:
        raise
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        raise InvalidCursor("cursor is malformed") from error
