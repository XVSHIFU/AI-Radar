"""Free deterministic classification; weak evidence may remain unclassified."""

import re
from urllib.parse import urlsplit

TITLE_RULES = {
    "industry": (
        r"\b(funding|fundrais\w*|acquisition|acquires?|merger|regulation|legislation|ipo)\b",
        r"融资|收购|并购|上市|监管|法案",
    ),
    "framework_sdk": (
        r"\b(sdk|framework|api client|python library|developer toolkit|software library|cuda|"
        r"pytorch|jax|tensorrt|gradio|nvidia flare|transformer engine|nvidia dynamo)\b",
        r"开发框架|开发套件|工具包|开源库",
    ),
    "agent_tool": (
        r"\b(agents?|agentic|agentcore|mcp|tool calling|coding assistant)\b",
        r"智能体|编程助手|工具调用",
    ),
    "research": (
        r"\b(benchmark\w*|research|paper|study|studies|evaluation|evaluating|dataset|theorem)\b",
        r"\b(understanding|investigating|measuring|rethinking|alignment)\b",
        r"论文|研究|评测|基准|数据集|实验|推理能力",
    ),
    "product": (
        r"\b(product|app|service) (launch|release|update)\b",
        r"\b(sagemaker|bedrock|copilot|vertex ai|chatgpt|foundry)\b",
        r"产品发布|应用上线|功能更新|服务上线",
    ),
}
TAG_CATEGORIES = {
    "model_release": {"model release", "model releases", "模型发布"},
    "agent_tool": {"agents", "agent", "agentic ai", "mcp", "智能体", "智能体工具"},
    "framework_sdk": {"sdk", "framework", "frameworks", "libraries", "框架与 sdk"},
    "research": {"research", "research paper", "benchmarks", "datasets", "研究", "论文"},
    "product": {"product", "product updates", "product launch", "产品"},
    "industry": {"industry", "funding", "regulation", "产业"},
}
MODEL = r"\b(?:models?|llms?|kimi|gpt|gemini|claude|llama|qwen|deepseek|mistral|nemotron)\b"
RELEASE = r"\b(?:introducing|announc\w*|releas\w*|launch\w*|available|availability|unveil\w*)\b"


def _scores(text: str, weight: int) -> dict[str, int]:
    scores = {category: 0 for category in TAG_CATEGORIES}
    for category, patterns in TITLE_RULES.items():
        if any(re.search(pattern, text, re.I) for pattern in patterns):
            scores[category] = max(1, weight - 2) if category == "product" else weight
    if (re.search(MODEL, text, re.I) and re.search(RELEASE, text, re.I)) or re.search(
        r"(?:发布|推出|上线).{0,20}(?:模型|大模型)|(?:模型|大模型).{0,20}(?:发布|上线)", text
    ):
        scores["model_release"] = weight + 2
    return scores


def classify_article(
    title: str,
    tags: tuple[str, ...] = (),
    *,
    summary: str | None = None,
    source_url: str | None = None,
) -> str | None:
    scores = _scores(title, 8)
    summary_scores = _scores((summary or "")[:1200], 2)
    for category in scores:
        scores[category] += min(summary_scores[category], 3)
    normalized_tags = {tag.casefold().strip() for tag in tags}
    for category, names in TAG_CATEGORIES.items():
        if normalized_tags & names:
            scores[category] += 5
    # Specific actions beat model names incidental to an SDK or business announcement.
    if scores["industry"] >= 8:
        return "industry"
    if re.search(r"\b(sdk|framework|api client)\b|开发框架|开发套件", title, re.I):
        return "framework_sdk"
    ranked = sorted(scores, key=lambda category: scores[category], reverse=True)
    first, second = ranked[:2]
    if scores[first] >= 5 and scores[first] - scores[second] >= 2:
        return first
    url = urlsplit(source_url or "")
    research_channel = url.hostname in {"research.google", "rss.arxiv.org", "export.arxiv.org"} or (
        url.hostname == "www.microsoft.com" and "/research/" in url.path
    )
    if research_channel and max(scores.values()) < 5:
        return "research"
    return None


GOOGLE_AI_TAGS = {
    "generative ai",
    "machine intelligence",
    "natural language processing",
    "open source models & datasets",
    "robotics",
    "responsible ai",
}


def accept_feed_entry(
    source_name: str, title: str, tags: tuple[str, ...], *, source_url: str | None = None
) -> bool:
    if not title.strip():
        return False
    if (
        urlsplit(source_url).hostname == "research.google"
        if source_url
        else source_name == "Google Research"
    ):
        return bool({tag.casefold() for tag in tags} & GOOGLE_AI_TAGS)
    return True
