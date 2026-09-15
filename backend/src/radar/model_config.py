from __future__ import annotations

import ipaddress
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

from .config import Settings

PROVIDER = "deepseek"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-flash"
PROTOCOL = "openai-compatible"

PRESETS = (
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": BASE_URL,
        "model": MODEL,
        "protocol": PROTOCOL,
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
        "protocol": PROTOCOL,
    },
    {
        "id": "qwen",
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "protocol": PROTOCOL,
    },
    {
        "id": "moonshot",
        "name": "Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2.6",
        "protocol": PROTOCOL,
    },
)
_PROVIDER_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")


class ModelConfigUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class EffectiveModelConfig:
    api_key: str | None
    enabled: bool
    max_tokens: int
    credential_changed_at: datetime | None
    provider: str
    base_url: str
    model: str


def normalize_provider(value: str) -> str:
    provider = value.strip().casefold()
    if not _PROVIDER_PATTERN.fullmatch(provider):
        raise ModelConfigUnavailable("模型供应商标识无效")
    return provider


def normalize_model(value: str) -> str:
    model = value.strip()
    if not model or len(model) > 200 or any(ord(char) < 32 for char in model):
        raise ModelConfigUnavailable("模型名称无效")
    return model


def normalize_base_url(value: str) -> str:
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError as exc:
        raise ModelConfigUnavailable("模型 API 地址无效") from exc
    if (
        parts.scheme.casefold() != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ModelConfigUnavailable("模型 API 地址必须是无鉴权信息、查询或片段的 HTTPS 地址")
    host = parts.hostname.casefold()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if host == "localhost" or host.endswith(".localhost"):
            raise ModelConfigUnavailable("模型 API 地址必须使用公网主机") from None
    else:
        if not address.is_global or address.is_multicast:
            raise ModelConfigUnavailable("模型 API 地址必须使用公网主机")
    rendered_host = f"[{host}]" if ":" in host else host
    netloc = f"{rendered_host}:{port}" if port else rendered_host
    path = "/" + parts.path.strip("/") if parts.path.strip("/") else ""
    return urlunsplit(("https", netloc, path, "", ""))


class ModelConfigStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._path = settings.model_config_path

    def read(self) -> EffectiveModelConfig:
        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return EffectiveModelConfig(
                api_key=self._settings.llm_api_key,
                enabled=bool(self._settings.llm_api_key),
                max_tokens=self._settings.llm_max_tokens,
                credential_changed_at=None,
                provider=normalize_provider(self._settings.llm_provider),
                base_url=normalize_base_url(self._settings.llm_base_url),
                model=normalize_model(self._settings.llm_model),
            )
        except (OSError, ValueError) as exc:
            raise ModelConfigUnavailable("无法读取已保存的模型配置") from exc
        if not isinstance(value, dict):
            raise ModelConfigUnavailable("已保存的模型配置格式无效")
        api_key = value.get("api_key")
        enabled = value.get("enabled")
        max_tokens = value.get("max_tokens")
        changed = value.get("credential_changed_at")
        if api_key is not None and not isinstance(api_key, str):
            raise ModelConfigUnavailable("已保存的模型密钥无效")
        if not isinstance(enabled, bool):
            raise ModelConfigUnavailable("已保存的模型开关无效")
        if (
            not isinstance(max_tokens, int)
            or isinstance(max_tokens, bool)
            or not 1 <= max_tokens <= 2000
        ):
            raise ModelConfigUnavailable("已保存的 max_tokens 无效")
        try:
            credential_changed_at = (
                datetime.fromisoformat(changed) if isinstance(changed, str) else None
            )
        except ValueError as exc:
            raise ModelConfigUnavailable("已保存的密钥更新时间无效") from exc
        if credential_changed_at is not None and credential_changed_at.tzinfo is None:
            raise ModelConfigUnavailable("密钥更新时间必须包含时区")
        # Files written before generic endpoints omitted these fields and are DeepSeek configs.
        provider = normalize_provider(
            value.get("provider", PROVIDER)
            if isinstance(value.get("provider", PROVIDER), str)
            else ""
        )
        base_url = normalize_base_url(
            value.get("base_url", BASE_URL)
            if isinstance(value.get("base_url", BASE_URL), str)
            else ""
        )
        model = normalize_model(
            value.get("model", MODEL) if isinstance(value.get("model", MODEL), str) else ""
        )
        return EffectiveModelConfig(
            api_key, enabled, max_tokens, credential_changed_at, provider, base_url, model
        )

    def update(
        self,
        *,
        api_key: str | None,
        enabled: bool,
        max_tokens: int,
        provider: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> EffectiveModelConfig:
        current = self.read()
        next_provider = normalize_provider(provider) if provider is not None else current.provider
        next_base = normalize_base_url(base_url) if base_url is not None else current.base_url
        next_model = normalize_model(model) if model is not None else current.model
        supplied_key = api_key.strip() if api_key is not None else ""
        endpoint_changed = next_base != current.base_url
        if endpoint_changed and (not supplied_key or supplied_key == current.api_key):
            raise ModelConfigUnavailable("更改模型 API 地址时必须同时提交新的 API Key")
        key = supplied_key or current.api_key
        key_changed = bool(supplied_key and supplied_key != current.api_key)
        if enabled and not key:
            raise ModelConfigUnavailable("启用模型时必须提供 API Key")
        changed_at = datetime.now(UTC) if key_changed else current.credential_changed_at
        config = EffectiveModelConfig(
            key, enabled, max_tokens, changed_at, next_provider, next_base, next_model
        )
        payload = {
            "api_key": config.api_key,
            "enabled": config.enabled,
            "max_tokens": config.max_tokens,
            "credential_changed_at": changed_at.isoformat() if changed_at is not None else None,
            "provider": config.provider,
            "base_url": config.base_url,
            "model": config.model,
        }
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self._path.with_name(f".{self._path.name}.{secrets.token_hex(8)}.tmp")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path)
            os.chmod(self._path, 0o600)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return config


def effective_model_settings(settings: Settings) -> Settings:
    config = ModelConfigStore(settings).read()
    return settings.model_copy(
        update={
            "llm_api_key": config.api_key if config.enabled else None,
            "llm_provider": config.provider,
            "llm_base_url": config.base_url,
            "llm_model": config.model,
            "llm_max_tokens": config.max_tokens,
        }
    )
