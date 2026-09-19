from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .config import Settings
from .content_api import (
    get_settings_row,
    latest_version_matches,
    make_export,
    parse_import,
    save_import,
)
from .content_gateway import discard, register
from .content_publisher import publish_extraction
from .extraction_schemas import ExtractionResult
from .model_config import ModelConfigStore
from .models import (
    ArticleVersionRow,
    ContentBatchRow,
    ContentDraftRow,
    ContentTaskRow,
    ContentUsageRow,
)


async def recover_abandoned(sessions: async_sessionmaker[AsyncSession]) -> None:
    """Never replay a potentially dispatched request after a process restart."""
    async with sessions() as session, session.begin():
        rows = list(
            (
                await session.scalars(
                    select(ContentTaskRow)
                    .where(ContentTaskRow.status == "auto_processing")
                    .with_for_update()
                )
            ).all()
        )
        for task in rows:
            task.status = "unknown"
            usage = await session.scalar(
                select(ContentUsageRow).where(ContentUsageRow.task_id == task.id).with_for_update()
            )
            if usage:
                usage.status = "unknown"
                usage.error_code = "process_restarted"
            if task.batch_id:
                batch = await session.get(ContentBatchRow, task.batch_id, with_for_update=True)
                if batch:
                    batch.status = "paused"
        # Queued batches are intentionally not restarted. A human can switch them to manual.
        batches = list(
            (
                await session.scalars(
                    select(ContentBatchRow)
                    .where(ContentBatchRow.status.in_(("queued", "running")))
                    .with_for_update()
                )
            ).all()
        )
        for batch in batches:
            batch.status = "paused"


async def _claim(
    sessions: async_sessionmaker[AsyncSession], settings: Settings, batch_id: UUID
) -> tuple[UUID, str, int] | None:
    async with sessions() as session, session.begin():
        limits = await get_settings_row(session, lock=True)
        batch = await session.get(ContentBatchRow, batch_id, with_for_update=True)
        if batch is None or batch.status not in {"queued", "running"}:
            return None
        if not limits.enabled or limits.profile_version != batch.profile_version:
            batch.status = "paused"
            return None
        task = await session.scalar(
            select(ContentTaskRow)
            .where(ContentTaskRow.batch_id == batch_id, ContentTaskRow.status == "queued_auto")
            .order_by(ContentTaskRow.created_at, ContentTaskRow.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if task is None:
            batch.status = "completed"
            return None
        # Global concurrency one, including abandoned reservations.
        active = await session.scalar(
            select(ContentUsageRow.id).where(ContentUsageRow.status == "reserved").limit(1)
        )
        if active is not None:
            batch.status = "budget_paused"
            task.status = "budget_paused"
            return None
        prior_usage = await session.scalar(
            select(ContentUsageRow.id).where(ContentUsageRow.task_id == task.id).limit(1)
        )
        if prior_usage is not None:
            task.status = "budget_paused"
            batch.status = "budget_paused"
            return None
        version = await session.get(ArticleVersionRow, task.article_version_id)
        if (
            version is None
            or version.content_hash != task.content_hash
            or not await latest_version_matches(session, version)
        ):
            task.status = "validation_failed"
            batch.status = "paused"
            return None
        try:
            prompt, scopes = make_export([(task, version)])
        except ValueError:
            task.status = "validation_failed"
            batch.status = "paused"
            return None
        input_reserved = len(prompt.encode("utf-8")) + 1024
        output_reserved = limits.max_output_tokens
        day = datetime.now(ZoneInfo(settings.business_timezone)).date()
        totals = (
            await session.execute(
                select(
                    func.count(ContentUsageRow.id),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    ContentUsageRow.status == "settled",
                                    func.coalesce(
                                        ContentUsageRow.actual_input_tokens,
                                        ContentUsageRow.reserved_input_tokens,
                                    ),
                                ),
                                else_=ContentUsageRow.reserved_input_tokens,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    ContentUsageRow.status == "settled",
                                    func.coalesce(
                                        ContentUsageRow.actual_output_tokens,
                                        ContentUsageRow.reserved_output_tokens,
                                    ),
                                ),
                                else_=ContentUsageRow.reserved_output_tokens,
                            )
                        ),
                        0,
                    ),
                ).where(ContentUsageRow.usage_day == day)
            )
        ).one()
        articles, spent_input, spent_output = (int(value) for value in totals)
        if (
            articles + 1 > limits.daily_article_limit
            or spent_input + input_reserved > limits.daily_input_tokens
            or spent_output + output_reserved > limits.daily_output_tokens
        ):
            batch.status = "budget_paused"
            task.status = "budget_paused"
            return None
        usage = ContentUsageRow(
            id=uuid4(),
            task_id=task.id,
            batch_id=batch.id,
            usage_day=day,
            reserved_input_tokens=input_reserved,
            reserved_output_tokens=output_reserved,
            status="reserved",
        )
        session.add(usage)
        task.export_scope = scopes[task.id]
        task.status = "auto_processing"
        task.claimed_at = datetime.now(UTC)
        batch.status = "running"
        return task.id, prompt, output_reserved


async def _finish_unknown(
    sessions: async_sessionmaker[AsyncSession], batch_id: UUID, task_id: UUID, code: str
) -> None:
    async with sessions() as session, session.begin():
        batch = await session.get(ContentBatchRow, batch_id, with_for_update=True)
        task = await session.get(ContentTaskRow, task_id, with_for_update=True)
        assert task is not None
        usage = await session.scalar(
            select(ContentUsageRow).where(ContentUsageRow.task_id == task_id).with_for_update()
        )
        assert usage is not None
        usage.status = "unknown"
        usage.error_code = code[:64]
        task.status = "unknown"
        if batch:
            batch.status = "paused"


async def _run_runtime(
    settings: Settings, capability: str, prompt: str, max_output: int
) -> dict[str, Any]:
    if not settings.research_runtime_token:
        raise RuntimeError("content runtime token missing")
    url = settings.research_runtime_url.rstrip("/") + "/v1/content"
    async with httpx.AsyncClient(timeout=100.0, trust_env=False) as client:
        async with client.stream(
            "POST",
            url,
            headers={"Authorization": f"Bearer {settings.research_runtime_token}"},
            json={"capability": capability, "prompt": prompt, "max_output": max_output},
        ) as response:
            response.raise_for_status()
            result: dict[str, Any] | None = None
            async for line in response.aiter_lines():
                if not line:
                    continue
                item = json.loads(line)
                if item.get("type") == "result":
                    result = item
            if result is None or result.get("status") != "completed":
                raise RuntimeError("content runtime result unknown")
            return result


async def _finish_success(
    sessions: async_sessionmaker[AsyncSession],
    batch_id: UUID,
    task_id: UUID,
    result: dict[str, Any],
) -> bool:
    raw = result.get("content")
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 32_000:
        await _finish_unknown(sessions, batch_id, task_id, "invalid_model_content")
        return False
    usage_value = result.get("usage")
    prompt_tokens = usage_value.get("input") if isinstance(usage_value, dict) else None
    output_tokens = usage_value.get("output") if isinstance(usage_value, dict) else None
    try:
        values = parse_import(raw)
        if (
            len(values) != 1
            or not isinstance(values[0], dict)
            or values[0].get("task_id") != str(task_id)
        ):
            raise ValueError("Model result task_id mismatch")
        content = {key: value for key, value in values[0].items() if key != "task_id"}
    except (ValueError, json.JSONDecodeError):
        content = {"relevant": True, "title_zh": "", "summary_zh": ""}
    async with sessions() as session, session.begin():
        batch = await session.get(ContentBatchRow, batch_id, with_for_update=True)
        assert batch is not None
        task = await session.get(ContentTaskRow, task_id, with_for_update=True)
        assert task is not None
        version = await session.get(ArticleVersionRow, task.article_version_id)
        assert version is not None
        usage = await session.scalar(
            select(ContentUsageRow).where(ContentUsageRow.task_id == task_id).with_for_update()
        )
        assert usage is not None
        if (
            isinstance(prompt_tokens, int)
            and not isinstance(prompt_tokens, bool)
            and isinstance(output_tokens, int)
            and not isinstance(output_tokens, bool)
            and prompt_tokens >= 0
            and output_tokens >= 0
        ):
            usage.actual_input_tokens = prompt_tokens
            usage.actual_output_tokens = output_tokens
            usage.status = "settled"
        else:
            usage.status = "unknown"
            usage.error_code = "usage_missing"
        saved = await save_import(session, task, version, content, mode="auto")
        if (
            batch.auto_publish
            and usage.status == "settled"
            and saved.get("status") == "needs_review"
        ):
            await session.flush()
            draft = await session.get(ContentDraftRow, task.draft_id, with_for_update=True)
            assert draft is not None
            extraction = ExtractionResult.model_validate(draft.content)
            event_id = await publish_extraction(
                session, version, extraction, alias_source="content_agent"
            )
            if event_id is not None:
                draft.event_id = event_id
                draft.status = "published"
                task.status = "published"
        if (
            usage.status == "unknown"
            or (
                usage.actual_input_tokens is not None
                and usage.actual_input_tokens > usage.reserved_input_tokens
            )
            or (
                usage.actual_output_tokens is not None
                and usage.actual_output_tokens > usage.reserved_output_tokens
            )
        ):
            batch.status = "paused"
            return False
        return batch.status == "running"


async def process_batch(
    sessions: async_sessionmaker[AsyncSession], settings: Settings, batch_id: UUID
) -> None:
    # Provider configuration is isolated from the public assistant's model.json.
    store = ModelConfigStore(
        settings.model_copy(
            update={
                "model_config_path": settings.model_config_path.with_name("content-model.json"),
                "llm_api_key": None,
            }
        )
    )
    try:
        config = store.read()
    except Exception:
        async with sessions() as session, session.begin():
            batch = await session.get(ContentBatchRow, batch_id, with_for_update=True)
            if batch and batch.status == "queued":
                batch.status = "paused"
        return
    while True:
        claimed = await _claim(sessions, settings, batch_id)
        if claimed is None:
            return
        task_id, prompt, max_output = claimed
        capability = await register(config, prompt, max_output)
        try:
            result = await _run_runtime(settings, capability, prompt, max_output)
        except Exception:
            await _finish_unknown(sessions, batch_id, task_id, "runtime_result_unknown")
            return
        finally:
            await discard(capability)
        try:
            continue_batch = await _finish_success(sessions, batch_id, task_id, result)
        except Exception:
            await _finish_unknown(sessions, batch_id, task_id, "result_processing_failed")
            return
        if not continue_batch:
            return
