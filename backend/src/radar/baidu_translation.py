"""General text translation only, with a durable local monthly spending guard."""

import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import time
from zoneinfo import ZoneInfo

import httpx

from .config import Settings
from .container_entry import private_value
from .summary_translation import TranslationProviderError

ENDPOINT = "https://fanyi-api.baidu.com/api/trans/vip/translate"


class TranslationQuotaExceeded(TranslationProviderError):
    pass


class TranslationRateLimited(TranslationProviderError):
    pass


@dataclass(frozen=True, repr=False)
class BaiduConfig:
    app_id: str
    secret: str
    monthly_limit: int
    ledger: Path


def configured_baidu(settings: Settings) -> BaiduConfig | None:
    path = settings.model_config_path.parent / "baidu_translation.json"
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8") if os.name == "nt" else private_value(path)
        value = json.loads(raw)
        app_id, secret = value["app_id"], value["secret"]
        limit = value.get("monthly_limit", 40_000)
        if not isinstance(app_id, str) or not app_id.isdecimal():
            raise ValueError
        if not isinstance(secret, str) or not secret.strip():
            raise ValueError
        if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= 40_000:
            raise ValueError
        return BaiduConfig(app_id, secret, limit, path.with_name("translation-usage.sqlite3"))
    except (OSError, ValueError, KeyError, TypeError):
        raise TranslationProviderError("Baidu configuration unavailable") from None


def reserve(config: BaiduConfig, characters: int, *, now: float | None = None) -> None:
    instant = time() if now is None else now
    month = datetime.fromtimestamp(instant, ZoneInfo("Asia/Shanghai")).strftime("%Y-%m")
    # Stable per APP ID, so changing the secret does not reset allowance.
    account = hashlib.sha256(config.app_id.encode()).hexdigest()
    config.ledger.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(config.ledger, timeout=5) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS usage (account TEXT, month TEXT, "
            "reserved INTEGER NOT NULL, last_request REAL NOT NULL, "
            "PRIMARY KEY(account,month))"
        )
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT reserved,last_request FROM usage WHERE account=? AND month=?", (account, month)
        ).fetchone()
        used, last = row if row else (0, 0)
        if characters < 1 or used + characters > config.monthly_limit:
            raise TranslationQuotaExceeded
        if instant - last < 1.1:
            raise TranslationRateLimited
        db.execute(
            "INSERT INTO usage VALUES (?,?,?,?) ON CONFLICT(account,month) "
            "DO UPDATE SET reserved=excluded.reserved,last_request=excluded.last_request",
            (account, month, used + characters, instant),
        )
        # Commit before sending. Timeouts/failures are not refunded: billing may have happened.
        db.commit()


async def translate_baidu(config: BaiduConfig, summary: str) -> str:
    characters = len(summary.encode("utf-16-le")) // 2
    if characters > 1000:
        raise TranslationProviderError("Summary exceeds standard translation request limit")
    try:
        await asyncio.to_thread(reserve, config, characters)
    except (sqlite3.Error, OSError):
        raise TranslationProviderError("Translation quota ledger unavailable") from None
    salt = secrets.token_hex(16)
    signature = hashlib.md5(
        (config.app_id + summary + salt + config.secret).encode(), usedforsecurity=False
    ).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
            response = await client.post(
                ENDPOINT,
                data={
                    "q": summary,
                    "from": "auto",
                    "to": "zh",
                    "appid": config.app_id,
                    "salt": salt,
                    "sign": signature,
                },
            )
            if response.status_code == 429:
                raise TranslationRateLimited
            response.raise_for_status()
            data = response.json()
        if str(data.get("error_code", "")) == "54003":
            raise TranslationRateLimited
        if data.get("error_code") or not isinstance(data.get("trans_result"), list):
            raise TranslationProviderError
        lines = [
            item["dst"]
            for item in data["trans_result"]
            if isinstance(item, dict) and isinstance(item.get("dst"), str) and item["dst"].strip()
        ]
        if not lines:
            raise TranslationProviderError
        return "\n".join(lines)
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise TranslationProviderError from None
