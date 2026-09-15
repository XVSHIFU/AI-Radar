from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from .config import Settings

PROVIDER = "deepseek"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-flash"


class ModelConfigUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class EffectiveModelConfig:
    api_key: str | None
    enabled: bool
    max_tokens: int
    credential_changed_at: datetime | None


class ModelConfigStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._path = settings.model_config_path

    def read(self) -> EffectiveModelConfig:
        try:
            value = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return EffectiveModelConfig(
                self._settings.llm_api_key,
                bool(self._settings.llm_api_key),
                self._settings.llm_max_tokens,
                None,
            )
        except (OSError, ValueError) as exc:
            raise ModelConfigUnavailable("Stored model configuration cannot be read") from exc
        if not isinstance(value, dict):
            raise ModelConfigUnavailable("Stored model configuration is invalid")
        api_key = value.get("api_key")
        enabled = value.get("enabled")
        max_tokens = value.get("max_tokens")
        changed = value.get("credential_changed_at")
        if api_key is not None and not isinstance(api_key, str):
            raise ModelConfigUnavailable("Stored model API key is invalid")
        if not isinstance(enabled, bool):
            raise ModelConfigUnavailable("Stored model enabled flag is invalid")
        if (
            not isinstance(max_tokens, int)
            or isinstance(max_tokens, bool)
            or not 1 <= max_tokens <= 2000
        ):
            raise ModelConfigUnavailable("Stored model max_tokens is invalid")
        try:
            credential_changed_at = (
                datetime.fromisoformat(changed) if isinstance(changed, str) else None
            )
        except ValueError as exc:
            raise ModelConfigUnavailable("Stored credential timestamp is invalid") from exc
        return EffectiveModelConfig(api_key, enabled, max_tokens, credential_changed_at)

    def update(
        self, *, api_key: str | None, enabled: bool, max_tokens: int
    ) -> EffectiveModelConfig:
        current = self.read()
        key = current.api_key if api_key is None or not api_key.strip() else api_key.strip()
        key_changed = bool(
            api_key is not None and api_key.strip() and api_key.strip() != current.api_key
        )
        changed_at = datetime.now(UTC) if key_changed else current.credential_changed_at
        payload = {
            "api_key": key,
            "enabled": enabled,
            "max_tokens": max_tokens,
            "credential_changed_at": (changed_at.isoformat() if changed_at is not None else None),
        }
        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self._path.with_name(f".{self._path.name}.{secrets.token_hex(8)}.tmp")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path)
            os.chmod(self._path, 0o600)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        return EffectiveModelConfig(key, enabled, max_tokens, changed_at)


def effective_model_settings(settings: Settings) -> Settings:
    """Return Settings with current server-side model configuration applied."""
    config = ModelConfigStore(settings).read()
    return settings.model_copy(
        update={
            "llm_api_key": config.api_key if config.enabled else None,
            "llm_base_url": BASE_URL,
            "llm_model": MODEL,
            "llm_max_tokens": config.max_tokens,
        }
    )
