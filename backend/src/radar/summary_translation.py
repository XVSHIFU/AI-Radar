"""Server-configured translation of stored source summaries only."""

from urllib.parse import urlsplit

import httpx

from .config import Settings
from .container_entry import private_value


class TranslationProviderError(Exception):
    """Provider is unavailable or returned an unusable translation."""


def configured_endpoint(settings: Settings) -> str | None:
    if settings.deeplx_endpoint_file is not None:
        try:
            endpoint = private_value(settings.deeplx_endpoint_file)
        except (OSError, UnicodeError, ValueError):
            return None
    elif settings.deeplx_endpoint is not None:
        endpoint = settings.deeplx_endpoint.get_secret_value()
    else:
        return None
    try:
        url = urlsplit(endpoint)
    except ValueError:
        return None
    if url.scheme != "https" or not url.hostname or url.username or url.password:
        return None
    return endpoint


async def translate_summary(endpoint: str, summary: str) -> str:
    try:
        async with httpx.AsyncClient(
            timeout=8.0, trust_env=False, follow_redirects=False
        ) as client:
            response = await client.post(
                endpoint,
                json={"text": summary, "source_lang": "auto", "target_lang": "ZH"},
            )
            response.raise_for_status()
            payload = response.json()
        translated = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(translated, str) or not translated.strip():
            raise TranslationProviderError
        return translated
    except (httpx.HTTPError, ValueError, TranslationProviderError):
        raise TranslationProviderError from None
