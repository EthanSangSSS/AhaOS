from __future__ import annotations

import re

from .config import DEFAULT_TAG_ALIASES, DEFAULT_TAG_KEYWORDS


def _normalize_tag(value: str) -> str:
    normalized = value.strip().strip(".,:;!?()[]{}<>\"'").lower()
    return DEFAULT_TAG_ALIASES.get(normalized, normalized)


def infer_tags(text: str, tag_keywords: set[str] | None = None) -> list[str]:
    """Extract explicit tags plus deterministic English and Chinese task concepts."""
    tags: set[str] = set()
    keywords = tag_keywords or DEFAULT_TAG_KEYWORDS
    lowered = text.lower()

    for raw_tag in re.findall(r"#([^\s#`]+)", text):
        normalized = _normalize_tag(raw_tag)
        if normalized:
            tags.add(normalized)
    for raw_tag in re.findall(r"`([^`\s]+)`", text):
        normalized = _normalize_tag(raw_tag)
        if normalized:
            tags.add(normalized)

    words = {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text)}
    tags.update(words.intersection(keywords))
    for phrase, normalized in DEFAULT_TAG_ALIASES.items():
        if phrase in lowered:
            tags.add(normalized)
    return sorted(tags)


def infer_memory_type(text: str) -> str:
    """Classify explicit operational language before falling back to semantic memory."""
    lowered = text.lower()
    if any(term in lowered for term in ("决定", "选择", "取舍", "decision", "decide", "choose")):
        return "decision"
    if any(
        term in lowered
        for term in (
            "必须",
            "应当",
            "需要执行",
            "流程",
            "步骤",
            "清单",
            "验证",
            "回滚",
            "must",
            "should",
            "checklist",
            "procedure",
            "verify",
            "run ",
        )
    ):
        return "procedural"
    if any(
        term in lowered
        for term in ("失败", "报错", "错误", "崩溃", "故障", "failure", "failed", "error", "bug", "incident")
    ):
        return "failure"
    if any(term in lowered for term in ("未解决", "待处理", "follow-up", "open loop", "todo", "pending")):
        return "open_loop"
    return "semantic"
