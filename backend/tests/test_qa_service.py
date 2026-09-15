from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from radar.deepseek_client import Completion, DeepSeekError, ProviderUsage
from radar.qa_service import QaError, QaService, validate_answer
from radar.repository import Page
from radar.schemas import AskRequest, Category, Event, Evidence, Filters, QueryPlan

EID = UUID("20000000-0000-4000-8000-000000000001")
VID = UUID("30000000-0000-4000-8000-000000000001")
XID = UUID("40000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 9, 15, tzinfo=UTC)


def event(i: int = 0) -> Event:
    return Event(
        id=UUID(int=EID.int + i),
        title_zh=f"事件{i}",
        summary_zh="摘要",
        category=Category.PRODUCT,
        importance=3,
        event_date=date(2026, 9, 15),
        date_precision="day",
        source_count=1,
        evidence_count=1,
        entities=[],
        content_version=1,
    )


def evidence(eid: UUID = EID, quote: str = "原文证据") -> Evidence:
    return Evidence(
        id=XID,
        event_id=eid,
        article_version_id=VID,
        paragraph_id="p1",
        quote_text=quote,
        source_url="https://db.example/source",
        title="数据库标题",
        verification_status="unverified",
        source_published_at=NOW,
        event_date=date(2026, 9, 15),
    )


def request(question: str = "请总结") -> AskRequest:
    return AskRequest(question=question, client_request_id="req-1")


def plan(filters: Filters | None = None) -> QueryPlan:
    return QueryPlan(
        intent="structured_summary",
        filters=filters or Filters(),
        timezone="Asia/Shanghai",
        business_date=date(2026, 9, 15),
        date_until_exclusive=None,
        constraints_origin={},
        free_text="",
        requires_clarification=False,
        clarification_candidates=[],
        warnings=[],
        data_mode="postgres",
        request_id="server-1",
    )


class Repo:
    def __init__(
        self, items: list[Event], total: int | None = None, ev: list[Evidence] | None = None
    ):
        self.items = items
        self.total = len(items) if total is None else total
        self.ev = [] if ev is None else ev

    async def list_events(self, filters: Filters, limit: int, cursor: str | None):
        self.filters = filters
        self.limit = limit
        return Page(self.items, self.total, None, NOW, "r")

    async def evidence_for(self, event_id: UUID):
        return self.ev


class Client:
    def __init__(self, content: str = '{"answer":"结论[1]","citation_indices":[1]}', error=None):
        self.content = content
        self.error = error
        self.calls = 0

    async def complete_json(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return Completion(self.content, "provider-1", ProviderUsage(11, 7, 18))


class NoSessions:
    pass


def service(client: Client) -> QaService:
    svc = QaService(NoSessions(), client)  # type: ignore[arg-type]
    svc.claim = AsyncMock(return_value=UUID(int=9))  # type: ignore[method-assign]
    svc.mark = AsyncMock()  # type: ignore[method-assign]
    return svc


@pytest.mark.asyncio
async def test_scope_is_preserved_and_citations_come_from_database():
    filters = Filters(category=Category.PRODUCT, event_ids=[EID])
    repo = Repo([event()], ev=[evidence()])
    svc = service(Client())
    result = await svc.answer(request(), plan(filters), repo)  # type: ignore[arg-type]
    assert repo.filters == filters and repo.limit == 20
    assert result["citations"] == [
        {
            "index": 1,
            "source_url": "https://db.example/source",
            "title": "数据库标题",
            "quote_text": "原文证据",
            "paragraph_id": "p1",
        }
    ]
    assert result["summarized_count"] == 1 and result["citation_count"] == 1


@pytest.mark.asyncio
async def test_partial_reports_real_scope_and_retrieval_count():
    repo = Repo([event(i) for i in range(20)], total=25, ev=[evidence()])
    svc = service(Client())
    result = await svc.answer(request(), plan(), repo)  # type: ignore[arg-type]
    assert (result["scope_total"], result["retrieved_count"], result["coverage"]) == (
        25,
        20,
        "partial",
    )


@pytest.mark.asyncio
async def test_coverage_is_partial_when_answer_cites_only_one_event_in_scope():
    repo = Repo([event(), event(1)], ev=[evidence()])
    svc = service(Client())
    result = await svc.answer(request(), plan(), repo)  # type: ignore[arg-type]
    assert result["scope_total"] == 2
    assert result["summarized_count"] == 1
    assert result["coverage"] == "partial"


@pytest.mark.asyncio
async def test_no_evidence_does_not_call_model_or_claim():
    client = Client()
    svc = service(client)
    result = await svc.answer(request(), plan(), Repo([event()]))  # type: ignore[arg-type]
    assert result["answer_status"] == "no_answer" and client.calls == 0
    svc.claim.assert_not_awaited()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_provider_failure_is_not_reported_as_no_answer_and_usage_is_recorded():
    completion = Completion("partial", "p", ProviderUsage(5, None, None))
    svc = service(
        Client(
            error=DeepSeekError(
                "bad", code="provider_http_500", stop_batch=False, completion=completion
            )
        )
    )
    with pytest.raises(QaError, match="Answer model failed") as caught:
        await svc.answer(request(), plan(), Repo([event()], ev=[evidence()]))  # type: ignore[arg-type]
    assert caught.value.code == "MODEL_FAILED"
    svc.mark.assert_awaited_once_with(UUID(int=9), "failed", completion, "provider_http_500")  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "raw",
    [
        '{"answer":"伪造 https://evil.example [1]","citation_indices":[1]}',
        '{"answer":"越界[2]","citation_indices":[2]}',
        '{"answer":"正文[1]","citation_indices":[1,2]}',
    ],
)
def test_citation_whitelist_rejects_urls_unknown_or_mismatched_indices(raw: str):
    with pytest.raises(ValueError):
        validate_answer(raw, 1)


@pytest.mark.asyncio
async def test_unknown_transport_marks_unknown_with_unknown_usage():
    svc = service(
        Client(error=DeepSeekError("unknown", code="unknown_transport_failure", stop_batch=False))
    )
    with pytest.raises(QaError) as caught:
        await svc.answer(request(), plan(), Repo([event()], ev=[evidence()]))  # type: ignore[arg-type]
    assert caught.value.code == "MODEL_OUTCOME_UNKNOWN" and caught.value.retryable is False
    svc.mark.assert_awaited_once_with(UUID(int=9), "unknown", None, "unknown_transport_failure")  # type: ignore[attr-defined]
