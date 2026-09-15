"""Anonymous ownership and private quota keys; never trust request-supplied IP headers."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
import secrets
from datetime import UTC, datetime, timedelta

TOKEN_NONCE = re.compile(r"[0-9a-f]{64}\Z")
SESSION_LIFETIME = timedelta(days=30)


class PublicIdentity:
    def __init__(self, secret: str) -> None:
        if len(secret.encode()) < 32:
            raise ValueError("public assistant secret must contain at least 32 bytes")
        self._secret = secret.encode()

    def digest(self, purpose: str, value: str) -> str:
        return hmac.new(
            self._secret, f"radar-public-v1:{purpose}:{value}".encode(), hashlib.sha256
        ).hexdigest()

    def issue(self, now: datetime | None = None) -> str:
        now = now or datetime.now(UTC)
        body = f"{secrets.token_hex(32)}.{int((now + SESSION_LIFETIME).timestamp())}"
        return f"{body}.{self.digest('cookie', body)}"

    def subject(self, token: str | None, now: datetime | None = None) -> str | None:
        if token is None or len(token) > 160:
            return None
        parts = token.split(".")
        if len(parts) != 3 or not TOKEN_NONCE.fullmatch(parts[0]):
            return None
        nonce, expiration, signature = parts
        if not TOKEN_NONCE.fullmatch(signature):
            return None
        if not expiration.isascii() or not expiration.isdecimal() or len(expiration) > 12:
            return None
        now = now or datetime.now(UTC)
        expiry = int(expiration)
        if not now.timestamp() < expiry <= (now + SESSION_LIFETIME).timestamp() + 60:
            return None
        if not hmac.compare_digest(signature, self.digest("cookie", f"{nonce}.{expiration}")):
            return None
        return self.digest("owner", nonce)

    def ip_key(self, address: str) -> str:
        ip = ipaddress.ip_address(address)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return self.digest("ip", ip.compressed)
