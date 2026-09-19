"""Conservative deterministic category hints for unverified feed articles."""

import re

CATEGORY_TERMS = {
    "model_release": (
        r"\b(model|llm) release\b",
        r"\b(gpt|gemini|claude|llama|qwen|deepseek)[ -]?\d",
    ),
    "agent_tool": (r"\b(ai |coding )?agent(s)?\b", r"\b(mcp|tool calling)\b"),
    "framework_sdk": (r"\b(sdk|framework|api client)\b",),
    "research": (r"\b(arxiv|research paper|benchmark study)\b",),
    "product": (r"\b(product|app) launch\b",),
    "industry": (r"\b(funding|acquisition|regulation)\b",),
}


def classify_article(title: str, tags: tuple[str, ...] = ()) -> str | None:
    text = " ".join((title, *tags)).casefold()
    matches = [
        category
        for category, patterns in CATEGORY_TERMS.items()
        if any(re.search(pattern, text) for pattern in patterns)
    ]
    return matches[0] if len(matches) == 1 else None


GOOGLE_AI_TAGS = {
    "generative ai",
    "machine intelligence",
    "natural language processing",
    "open source models & datasets",
    "robotics",
    "responsible ai",
}


def accept_feed_entry(source_name: str, title: str, tags: tuple[str, ...]) -> bool:
    if not title.strip():
        return False
    if source_name == "Google Research":
        return bool({tag.casefold() for tag in tags} & GOOGLE_AI_TAGS)
    return True
