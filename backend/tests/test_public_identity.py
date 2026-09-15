from datetime import UTC, datetime, timedelta

import pytest

from radar.public_identity import PublicIdentity


def test_signed_anonymous_ownership_and_tamper_rejection():
    identity = PublicIdentity("a" * 32)
    now = datetime(2026, 9, 16, tzinfo=UTC)
    token = identity.issue(now)
    assert identity.subject(token, now)
    assert identity.subject(token, now) != identity.subject(identity.issue(now), now)
    assert identity.subject(token + "x", now) is None
    assert identity.subject(token.rsplit(".", 1)[0] + ".非法签名", now) is None
    assert identity.subject(token.replace(token[:4], "ffff", 1), now) is None
    assert identity.subject(token, now + timedelta(days=30)) is None
    assert PublicIdentity("b" * 32).subject(token, now) is None


@pytest.mark.parametrize("token", [None, "", "a.b.c", "a" * 200, "a" * 64 + ".９９９.sig"])
def test_malformed_cookie_is_not_an_identity(token):
    assert PublicIdentity("a" * 32).subject(token) is None


def test_ip_normalization_and_domain_separation():
    identity = PublicIdentity("a" * 32)
    assert identity.ip_key("::ffff:192.0.2.1") == identity.ip_key("192.0.2.1")
    assert identity.ip_key("2001:db8::1") == identity.ip_key("2001:0db8:0:0:0:0:0:1")
    assert identity.ip_key("192.0.2.1") != identity.ip_key("192.0.2.2")
    assert identity.ip_key("192.0.2.1") != identity.digest("owner", "192.0.2.1")
    with pytest.raises(ValueError):
        identity.ip_key("unknown")
    with pytest.raises(ValueError):
        PublicIdentity("short")
