"""Scoring protocol tests use fabricated reviews, never real evaluation results."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "research_quality", ROOT / "scripts/research_quality.py"
)
quality = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quality)
CORPUS = json.loads(quality.CORPUS.read_text(encoding="utf-8"))


def fake_reviewed_matrix():
    result = quality.template(CORPUS)
    for variant in result["variants"].values():
        variant["configuration"] = {
            "provider": "fixture",
            "model": "fixture",
            "max_output_tokens": 512,
            "code_revision": "test-only-not-an-evaluation",
        }
        for row, case in zip(variant["cases"], CORPUS["cases"], strict=True):
            cited = case["required"].get("citations_required", False)
            outcome = case["required"].get("outcome")
            status = {"cancelled": "cancelled", "reject_unregistered_citation": "failed"}.get(
                outcome, "completed"
            )
            row["execution"] = {
                "status": status,
                "answer": "test-only fabricated answer",
                "citations": [{"index": 1}] if cited else [],
                "metrics": {
                    "model_calls": 1,
                    "input_tokens": None,
                    "output_tokens": None,
                    "first_token_ms": None,
                    "duration_ms": 1,
                },
                "client_checks": {k: True for k in case.get("setup", {}).get("check", [])},
            }
            row["review"] = {
                "reviewer": "unit-test fixture, not a human acceptance",
                "all_factual_claims_reviewed": True,
                "task_completed": True,
                "notes": "fabricated test input only",
                "claims": [{"text": "test claim", "supported": True, "evidence": "test fixture"}]
                if cited
                else [],
                "citation_checks": [{"index": 1, "located": True, "locator": "test fixture"}]
                if cited
                else [],
            }
    return result


def test_frozen_oracles_validate_without_network_or_models():
    assert quality.validate(CORPUS)["cases"] == 40
    assert quality.validate(CORPUS)["evaluation_status"] == "not_run"
    assert len(quality.selected(CORPUS["events"], {})) == 12
    assert (
        len(
            quality.selected(
                CORPUS["events"],
                {
                    "date_from": "2026-09-01",
                    "date_to": "2026-09-30",
                },
            )
        )
        == 7
    )


def test_corpus_mutation_cannot_silently_change_the_baseline():
    changed = copy.deepcopy(CORPUS)
    changed["cases"][16]["required"]["count"] = 999
    with pytest.raises(ValueError, match="hash mismatch"):
        quality.validate(changed)


def test_empty_template_and_zero_denominators_are_incomplete():
    report = quality.score(CORPUS, quality.template(CORPUS))
    assert report["status"] == "incomplete"
    assert report["quality_release_eligible"] is False
    assert report["variants"]["agent"]["rates"]["semantic_consistency"] is None
    assert len(report["variants"]["agent"]["missing_reviews"]) == 40


def test_equal_quality_is_not_an_improvement_and_usage_stays_unknown():
    report = quality.score(CORPUS, fake_reviewed_matrix())
    assert report["status"] == "reviewed"
    assert report["variants"]["agent"]["status"] == "passed"
    assert report["quality_release_eligible"] is False
    assert report["variants"]["agent"]["usage"]["input_tokens_unknown_cases"] == 40
    assert report["variants"]["agent"]["usage"]["input_tokens_known"] == 0


def test_comparison_needs_all_40_and_same_model_conditions():
    results = fake_reviewed_matrix()
    results["variants"]["agent"]["configuration"]["model"] = "different"
    assert quality.score(CORPUS, results)["status"] == "incomplete"
    results["variants"]["legacy"]["cases"].pop()
    with pytest.raises(ValueError, match="case results"):
        quality.score(CORPUS, results)


def test_explicit_task_improvement_and_thresholds_are_required():
    results = fake_reviewed_matrix()
    for row in results["variants"]["legacy"]["cases"][:5]:
        row["review"]["task_completed"] = False
    for row in results["variants"]["agent"]["cases"][:4]:
        row["review"]["task_completed"] = False
    assert quality.score(CORPUS, results)["quality_release_eligible"] is True
    results["variants"]["agent"]["cases"][4]["review"]["task_completed"] = False
    assert quality.score(CORPUS, results)["quality_release_eligible"] is False


@pytest.mark.parametrize("change", ["citation", "claim", "boolean", "timing", "client_check"])
def test_reviews_cannot_hide_protocol_or_measurement_failures(change):
    results = fake_reviewed_matrix()
    row = results["variants"]["agent"]["cases"][0]
    if change == "citation":
        row["review"]["citation_checks"][0]["located"] = False
        report = quality.score(CORPUS, results)
        assert report["variants"]["agent"]["status"] == "failed"
    elif change == "claim":
        for item in results["variants"]["agent"]["cases"][:5]:
            item["review"]["claims"][0]["supported"] = False
        assert quality.score(CORPUS, results)["variants"]["agent"]["status"] == "failed"
    elif change == "client_check":
        results["variants"]["agent"]["cases"][34]["execution"]["client_checks"] = {}
        assert (
            quality.score(CORPUS, results)["variants"]["agent"]["rates"]["task_completion"] == 0.975
        )
    else:
        if change == "boolean":
            row["review"]["task_completed"] = "true"
        else:
            row["execution"]["metrics"]["duration_ms"] = float("nan")
        with pytest.raises(ValueError):
            quality.score(CORPUS, results)


def test_drafts_and_safety_failures_cannot_be_approved_as_success():
    results = fake_reviewed_matrix()
    row = results["variants"]["agent"]["cases"][39]
    row["execution"]["status"] = "failed"
    report = quality.score(CORPUS, results)["variants"]["agent"]
    assert report["status"] == "failed"
    assert report["mandatory_failures"] == ["Q40"]
    assert report["rates"]["task_completion"] == 0.975
    assert report["timings"]["duration_ms"]["p95"] == 1
    assert report["timings"]["first_token_ms"]["unknown"] == 40
