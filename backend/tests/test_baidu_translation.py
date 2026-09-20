from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from radar.baidu_translation import (
    BaiduConfig,
    TranslationQuotaExceeded,
    TranslationRateLimited,
    reserve,
    translate_baidu,
)
from radar.summary_translation import TranslationProviderError


def test_usage_survives_new_config_and_secret_rotation(tmp_path: Path) -> None:
    config = BaiduConfig("123", "test-secret", 10, tmp_path / "usage.sqlite3")
    reserve(config, 6, now=1_780_000_000)
    restarted = replace(config, secret="rotated-secret")
    with pytest.raises(TranslationQuotaExceeded):
        reserve(restarted, 5, now=1_780_000_002)
    reserve(restarted, 4, now=1_780_000_004)
    with pytest.raises(TranslationQuotaExceeded):
        reserve(restarted, 1, now=1_780_000_006)


def test_rate_rejection_does_not_consume_allowance(tmp_path: Path) -> None:
    config = BaiduConfig("123", "test-secret", 10, tmp_path / "usage.sqlite3")
    reserve(config, 5, now=1_780_000_000)
    with pytest.raises(TranslationRateLimited):
        reserve(config, 5, now=1_780_000_000.5)
    reserve(config, 5, now=1_780_000_002)


async def test_timeout_reservation_prevents_another_paid_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = BaiduConfig("123", "test-secret", 5, tmp_path / "usage.sqlite3")
    calls = 0

    async def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("simulated timeout")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail)
    with pytest.raises(TranslationProviderError):
        await translate_baidu(config, "hello")
    with pytest.raises(TranslationQuotaExceeded):
        await translate_baidu(config, "hello")
    assert calls == 1
