import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from difflib import get_close_matches
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .normalize import normalize_text
from .schemas import Category, ClarificationCandidate, ConversationMessage, Filters, QueryPlan


class InvalidTimezone(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedEntity:
    label: str
    entity_id: UUID


@dataclass(frozen=True)
class EntityResolution:
    resolved: list[ResolvedEntity]
    ambiguous: list[ResolvedEntity]
    matched_terms: list[str]
    matched_spans: list[tuple[int, int]]


class EntityResolver(Protocol):
    async def resolve_entities(self, text: str) -> EntityResolution: ...


CATEGORY_ALIASES = {
    "model_release": Category.MODEL_RELEASE,
    "模型发布": Category.MODEL_RELEASE,
    "agent_tool": Category.AGENT_TOOL,
    "agent工具": Category.AGENT_TOOL,
    "agent 工具": Category.AGENT_TOOL,
    "agent与工具": Category.AGENT_TOOL,
    "智能体工具": Category.AGENT_TOOL,
    "framework_sdk": Category.FRAMEWORK_SDK,
    "框架sdk": Category.FRAMEWORK_SDK,
    "research": Category.RESEARCH,
    "研究": Category.RESEARCH,
    "product": Category.PRODUCT,
    "产品": Category.PRODUCT,
    "industry": Category.INDUSTRY,
    "行业": Category.INDUSTRY,
    "unclassified": Category.UNCLASSIFIED,
    "未分类": Category.UNCLASSIFIED,
}
GENERIC_WORDS = (
    "这些日期",
    "这些事件",
    "这些",
    "这几个",
    "它们",
    "上述",
    "前述",
    "前面",
    "之前",
    "刚才",
    "上面的",
    "该事件",
    "还有",
    "继续",
    "有哪些",
    "有什么",
    "请问",
    "请",
    "相关",
    "进展",
    "事件",
    "新闻",
    "总结",
    "概括",
    "分析",
    "解释",
    "说明",
    "这条",
    "类",
    "的",
    "或",
    "和",
    "？",
    "?",
)
ABSOLUTE_RANGE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})\s*(?:至|到|~|—|-)\s*(?:(\d{4})-)?(\d{2})-(\d{2})"
)
SINGLE_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?![\d-])")
RELATIVE_DATE_TERMS = ("最近7天", "最近一周", "今天", "昨天", "本周", "上周", "过去24小时")
FOLLOW_UP_REFERENCES = (
    "这些",
    "这几个",
    "它们",
    "上述",
    "前述",
    "前面",
    "之前",
    "刚才",
    "上面的",
    "该事件",
    "还有",
    "继续",
)
HISTORY_ACKNOWLEDGEMENTS = {
    "好",
    "好的",
    "好吧",
    "嗯",
    "收到",
    "明白",
    "明白了",
    "知道了",
    "谢谢",
    "谢谢你",
    "感谢",
}


def normalize_query(value: str) -> str:
    return normalize_text(value)


def _date_range(text: str, business_date: date) -> tuple[date, date, str | None]:
    match = ABSOLUTE_RANGE.search(text)
    if match:
        start = date(int(match[1]), int(match[2]), int(match[3]))
        end_year = int(match[4]) if match[4] else start.year
        end = date(end_year, int(match[5]), int(match[6]))
        if match[4] is None and end < start:
            if start.month == 12 and end.month == 1:
                end = date(start.year + 1, int(match[5]), int(match[6]))
            else:
                raise ValueError("question date range is inverted")
        if end < start:
            raise ValueError("question date range is inverted")
        return start, end, match.group(0)
    single = SINGLE_DATE.search(text)
    if single:
        value = date(int(single[1]), int(single[2]), int(single[3]))
        return value, value, single.group(0)
    relative = (
        ("最近7天", business_date - timedelta(days=6), business_date),
        ("最近一周", business_date - timedelta(days=6), business_date),
        ("今天", business_date, business_date),
        ("昨天", business_date - timedelta(days=1), business_date - timedelta(days=1)),
        ("本周", business_date - timedelta(days=business_date.weekday()), business_date),
        (
            "上周",
            business_date - timedelta(days=business_date.weekday() + 7),
            business_date - timedelta(days=business_date.weekday() + 1),
        ),
    )
    for term, start, end in relative:
        if term in text:
            return start, end, term
    return business_date, business_date, None


def _date_terms(text: str) -> list[str]:
    terms = [term for term in RELATIVE_DATE_TERMS if term in text]
    absolute = ABSOLUTE_RANGE.search(text)
    dates = (
        [absolute.group(0)]
        if absolute
        else [match.group(0) for match in SINGLE_DATE.finditer(text)]
    )
    return dates + terms


class QueryPlanner:
    async def parse(
        self,
        question: str,
        filters: Filters,
        timezone: str,
        clock: datetime,
        entity_resolver: EntityResolver,
        history: list[ConversationMessage] | None = None,
    ) -> QueryPlan:
        if clock.tzinfo is None or clock.utcoffset() is None:
            raise ValueError("clock must be timezone-aware")
        try:
            zone = ZoneInfo(timezone)
        except ZoneInfoNotFoundError as exc:
            raise InvalidTimezone(timezone) from exc
        business_date = clock.astimezone(zone).date()
        normalized = normalize_query(question)
        inferred = Filters()
        origins: dict[str, str] = {}
        warnings: list[str] = []
        consumed: list[str] = []
        requires_clarification = "过去24小时" in normalized
        candidates = (
            [ClarificationCandidate(label="改用最近1个业务日（日精度）", entity_id=None)]
            if requires_clarification
            else []
        )
        if requires_clarification:
            consumed.append("过去24小时")

        date_terms = _date_terms(normalized)
        start, end, date_term = _date_range(normalized, business_date)
        if date_term is not None:
            inferred.date_from = start
            inferred.date_to = end
            consumed.append(date_term)
        if len(date_terms) > 1:
            requires_clarification = True
            warnings.append("问题中有多个日期限制，请选择一个日期范围")
            candidates.append(ClarificationCandidate(label="请选择一个日期范围", entity_id=None))
        resolution = await entity_resolver.resolve_entities(normalized)
        category_characters = list(normalized)
        for start_index, end_index in resolution.matched_spans:
            category_characters[start_index:end_index] = " " * (end_index - start_index)
        category_text = "".join(category_characters)
        category_matches: list[tuple[str, Category]] = []
        for alias in sorted(CATEGORY_ALIASES, key=len, reverse=True):
            if alias in category_text:
                category_matches.append((alias, CATEGORY_ALIASES[alias]))
                consumed.append(alias)
        if category_matches:
            inferred.category = category_matches[0][1]
        if len({category for _, category in category_matches}) > 1:
            requires_clarification = True
            warnings.append("问题中有多个事件分类，请选择一个分类")
            candidates.append(ClarificationCandidate(label="请选择一个事件分类", entity_id=None))

        if resolution.resolved:
            inferred.entity_ids = [item.entity_id for item in resolution.resolved]
            inferred.entity_match = "any" if "或" in normalized else "all"
            consumed.extend(resolution.matched_terms)
        if resolution.ambiguous:
            requires_clarification = True
            candidates.extend(
                ClarificationCandidate(label=item.label, entity_id=item.entity_id)
                for item in resolution.ambiguous
            )

        follow_up_requested = any(term in normalized for term in FOLLOW_UP_REFERENCES) or (
            normalized.endswith("呢")
            and bool(
                inferred.date_from or inferred.category or inferred.entity_ids or inferred.event_ids
            )
        )

        combined = filters.model_copy(deep=True)
        for field in ("date_from", "date_to", "category"):
            explicit = getattr(filters, field)
            inferred_value = getattr(inferred, field)
            if explicit is not None:
                origins[field] = "request"
                if inferred_value is not None and inferred_value != explicit:
                    warnings.append(f"请求参数 {field} 已覆盖问题中识别出的值")
            elif inferred_value is not None:
                setattr(combined, field, inferred_value)
                origins[field] = "question"
        explicit_entity_match = "entity_match" in filters.model_fields_set
        if filters.entity_ids:
            origins["entity_ids"] = "request"
            if inferred.entity_ids and set(filters.entity_ids) != set(inferred.entity_ids):
                warnings.append("请求参数 entity_ids 已覆盖问题中识别出的实体")
        elif inferred.entity_ids:
            combined.entity_ids = inferred.entity_ids
            origins["entity_ids"] = "question"
        if explicit_entity_match:
            origins["entity_match"] = "request"
            if inferred.entity_ids and filters.entity_match != inferred.entity_match:
                warnings.append("请求参数 entity_match 已覆盖问题中识别出的匹配方式")
        elif inferred.entity_ids:
            combined.entity_match = inferred.entity_match
            origins["entity_match"] = "question"
        if filters.q:
            origins["q"] = "request"
            normalized_q = normalize_query(filters.q)
            if normalized_q and normalized_q in normalized:
                consumed.append(normalized_q)
        if filters.min_importance is not None:
            origins["min_importance"] = "request"
        if filters.event_ids:
            origins["event_ids"] = "request"

        residual = normalized
        for term in sorted(set(consumed), key=len, reverse=True):
            residual = residual.replace(term, " ")
        for word in GENERIC_WORDS:
            residual = residual.replace(word, " ")
        if follow_up_requested:
            residual = re.sub(r"(^|\s)(?:那|再|呢)(?=\s|$)", " ", residual)
            residual = residual.strip("那再呢 ")
        residual = re.sub(r"[\s,，。:：]+", " ", residual).strip()
        combined = Filters.model_validate(combined.model_dump())
        if combined.date_to == date.max:
            raise ValueError("date_to is too large for an exclusive upper bound")
        date_until = combined.date_to + timedelta(days=1) if combined.date_to else None
        plan = QueryPlan(
            intent="structured_list",
            filters=combined,
            timezone=timezone,
            business_date=business_date,
            date_until_exclusive=date_until,
            constraints_origin=origins,
            free_text=residual,
            requires_clarification=requires_clarification,
            clarification_candidates=candidates,
            warnings=warnings,
            entity_roles=["subject", "product"],
        )
        return await self._apply_history(
            plan,
            history or [],
            follow_up_requested,
            timezone,
            clock,
            entity_resolver,
        )

    async def _apply_history(
        self,
        plan: QueryPlan,
        history: list[ConversationMessage],
        follow_up_requested: bool,
        timezone: str,
        clock: datetime,
        entity_resolver: EntityResolver,
    ) -> QueryPlan:
        warnings = list(plan.warnings)
        assistant_turns = sum(item.role == "assistant" for item in history)
        if assistant_turns:
            warnings.append(f"已忽略 {assistant_turns} 条 assistant 历史中的筛选、事实与证据")
        if not follow_up_requested:
            if history:
                warnings.append("当前问题按独立问题处理，未继承历史筛选")
            return plan.model_copy(
                update={
                    "warnings": warnings,
                    "history_turns_considered": len(history),
                }
            )

        inherited: dict[str, object] | None = None
        unsafe_relative_date = False
        uncertain_history = False
        for message in reversed(history):
            if message.role != "user":
                continue
            historical_text = normalize_query(message.content)
            acknowledgement = historical_text.strip(" ,，。!！?？")
            if acknowledgement in HISTORY_ACKNOWLEDGEMENTS and message.filters is None:
                continue
            historical = await self.parse(
                message.content,
                message.filters or Filters(),
                timezone,
                clock,
                entity_resolver,
                history=[],
            )
            values: dict[str, object] = {}
            for field in (
                "q",
                "category",
                "date_from",
                "date_to",
                "min_importance",
                "entity_ids",
                "event_ids",
            ):
                if field in historical.constraints_origin:
                    value = getattr(historical.filters, field)
                    if value is not None and value != []:
                        values[field] = value
            if "entity_ids" in values:
                values["entity_match"] = historical.filters.entity_match

            has_relative_date = any(term in historical_text for term in RELATIVE_DATE_TERMS)
            frozen_date = bool(
                message.filters
                and message.filters.date_from is not None
                and message.filters.date_to is not None
            )
            if has_relative_date and not frozen_date:
                values.pop("date_from", None)
                values.pop("date_to", None)
                unsafe_relative_date = True
            uncertain_history = bool(historical.requires_clarification or historical.free_text)
            if values or unsafe_relative_date or uncertain_history:
                inherited = values
                break

        combined = plan.filters.model_copy(deep=True)
        origins = dict(plan.constraints_origin)
        used = False
        if inherited is not None:
            for field, value in inherited.items():
                if field in origins:
                    continue
                setattr(combined, field, value)
                origins[field] = "history"
                used = True
        combined = Filters.model_validate(combined.model_dump())

        requires_clarification = plan.requires_clarification
        candidates = list(plan.clarification_candidates)
        if unsafe_relative_date:
            requires_clarification = True
            warnings.append("历史相对日期没有冻结绝对范围，未按当前时间重新解释")
            candidates.append(
                ClarificationCandidate(label="请重新选择绝对日期范围", entity_id=None)
            )
        if uncertain_history:
            requires_clarification = True
            warnings.append("最近有关用户轮仍有未解析或待澄清约束，未将其视为确定范围")
            candidates.append(
                ClarificationCandidate(label="请重新说明上一轮的完整约束", entity_id=None)
            )
        has_scope = bool(
            combined.q
            or combined.category
            or combined.date_from
            or combined.date_to
            or combined.min_importance
            or combined.entity_ids
            or combined.event_ids
        )
        if inherited is None and not has_scope:
            requires_clarification = True
            warnings.append("追问没有可继承的用户轮筛选")
            candidates.append(
                ClarificationCandidate(label="请说明要追问的事件或筛选范围", entity_id=None)
            )
        if combined.date_to == date.max:
            raise ValueError("date_to is too large for an exclusive upper bound")
        date_until = combined.date_to + timedelta(days=1) if combined.date_to else None

        return plan.model_copy(
            update={
                "intent": "follow_up" if used else plan.intent,
                "filters": combined,
                "date_until_exclusive": date_until,
                "constraints_origin": origins,
                "requires_clarification": requires_clarification,
                "clarification_candidates": candidates,
                "warnings": warnings,
                "history_turns_considered": len(history),
                "history_user_turns_used": 1 if used else 0,
            }
        )


def _ascii_word_character(value: str) -> bool:
    return value.isascii() and (value.isalnum() or value == "_")


def resolve_confirmed_entities(
    normalized: str, aliases: dict[str, list[ResolvedEntity]]
) -> EntityResolution:
    spans: list[tuple[int, int, str]] = []
    for alias in aliases:
        if not alias:
            continue
        for match in re.finditer(re.escape(alias), normalized):
            start, end = match.span()
            if (
                _ascii_word_character(alias[0])
                and start
                and _ascii_word_character(normalized[start - 1])
            ):
                continue
            if (
                _ascii_word_character(alias[-1])
                and end < len(normalized)
                and _ascii_word_character(normalized[end])
            ):
                continue
            spans.append((start, end, alias))
    selected: list[tuple[int, int, str]] = []
    for candidate in sorted(spans, key=lambda item: (-(item[1] - item[0]), item[0])):
        if any(candidate[0] < end and start < candidate[1] for start, end, _ in selected):
            continue
        selected.append(candidate)
    resolved: dict[UUID, ResolvedEntity] = {}
    ambiguous: dict[UUID, ResolvedEntity] = {}
    matched_terms: list[str] = []
    for _start, _end, alias in sorted(selected):
        matched_terms.append(alias)
        distinct = {item.entity_id: item for item in aliases[alias]}
        if len(distinct) == 1:
            item = next(iter(distinct.values()))
            resolved[item.entity_id] = item
        else:
            ambiguous.update(distinct)
    if not resolved and not ambiguous and " " not in normalized:
        ambiguous = {item.entity_id: item for item in fuzzy_candidates(normalized, aliases)}
    return EntityResolution(
        list(resolved.values()),
        list(ambiguous.values()),
        matched_terms,
        [(start, end) for start, end, _alias in selected],
    )


def fuzzy_candidates(term: str, aliases: dict[str, list[ResolvedEntity]]) -> list[ResolvedEntity]:
    matches = get_close_matches(term, aliases, n=3, cutoff=0.75)
    return [item for match in matches for item in aliases[match]]
