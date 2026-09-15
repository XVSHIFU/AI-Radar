from datetime import date

import pytest

from radar.extraction_schemas import ExtractionResult


def payload(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "relevant": True,
        "title_zh": "发布新模型",
        "summary_zh": "公司发布了一个新模型。",
        "category": "model_release",
        "importance": 3,
        "entities": [{"canonical_name": "Example", "entity_type": "company", "role": "subject"}],
        "evidence": [{"paragraph_id": "p-1", "quote_text": "Released on 2026-09-01."}],
    }
    value.update(updates)
    return value


def test_unknown_event_date_does_not_fall_back_to_report_date() -> None:
    extraction = ExtractionResult.model_validate(payload())
    extraction.validate_publishable({"p-1": "Released on 2026-09-01."})
    assert extraction.event_date is None
    assert extraction.date_precision == "unknown"
    assert extraction.date_basis == "unknown"


def test_known_event_date_requires_frozen_date_evidence() -> None:
    extraction = ExtractionResult.model_validate(
        payload(
            event_date="2026-09-01",
            date_precision="day",
            date_basis="explicit_body",
            date_evidence_paragraph_id="p-2",
        )
    )
    with pytest.raises(ValueError, match="date evidence"):
        extraction.validate_publishable({"p-1": "Released on 2026-09-01."})


def test_known_event_date_accepts_matching_frozen_evidence() -> None:
    extraction = ExtractionResult.model_validate(
        payload(
            event_date="2026-09-01",
            date_precision="day",
            date_basis="explicit_body",
            date_evidence_paragraph_id="p-1",
        )
    )
    extraction.validate_publishable({"p-1": "Released on 2026-09-01."})
    assert extraction.event_date == date(2026, 9, 1)
