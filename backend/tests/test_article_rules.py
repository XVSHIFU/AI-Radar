import pytest
from radar.article_rules import accept_feed_entry, classify_article


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Introducing Kimi K3 on Amazon Bedrock", "model_release"),
        ("Evaluating Kimi K3 against Claude on a new benchmark", "research"),
        ("New SDK for Claude agent applications", "framework_sdk"),
        ("Agent startup announces funding with a new model", "industry"),
        ("Optimizing cost with Amazon Bedrock prompt caching", "product"),
        ("Building an agentic platform on Amazon Bedrock AgentCore", "agent_tool"),
        ("CUDA Toolkit adds Windows on Arm support", "framework_sdk"),
        ("发布新一代大模型", "model_release"),
        ("今日随笔", None),
    ],
)
def test_classifies_subject_instead_of_incidental_model_name(title, expected):
    assert classify_article(title) == expected


def test_tags_can_classify_a_title_without_keywords():
    assert classify_article("A new approach", ("Research",)) == "research"


def test_summary_and_research_channel_are_weak_evidence():
    assert classify_article("A new approach", summary="Our product uses a model.") is None
    assert (
        classify_article("A new approach", source_url="https://research.google/blog/rss/")
        == "research"
    )
    assert (
        classify_article("A new approach", source_url="https://aws.amazon.com/blogs/feed/") is None
    )
    assert (
        classify_article("SDK release", source_url="https://research.google/blog/rss/")
        == "framework_sdk"
    )


def test_source_rename_does_not_change_google_filter():
    assert not accept_feed_entry(
        "Renamed", "Unrelated article", (), source_url="https://research.google/blog/rss/"
    )
    assert accept_feed_entry(
        "Renamed", "Research", ("Generative AI",), source_url="https://research.google/blog/rss/"
    )
