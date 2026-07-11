from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_TAG_KEYWORDS = {
    "agent",
    "cache",
    "cron",
    "database",
    "handoff",
    "incident",
    "local",
    "memory",
    "pilot",
    "release",
    "report",
    "review",
    "rollback",
    "test",
    "validation",
    "workflow",
    "procedure",
    "failure",
    "deploy",
    "migration",
}

# Normalize common Chinese task language into the existing portable tag space.
# The pilot remains deterministic and does not depend on an external language model.
DEFAULT_TAG_ALIASES = {
    "发布": "release",
    "上线": "release",
    "部署": "deploy",
    "验证": "validation",
    "检查": "validation",
    "测试": "test",
    "回滚": "rollback",
    "迁移": "migration",
    "流程": "procedure",
    "清单": "procedure",
    "失败": "failure",
    "报错": "failure",
    "错误": "failure",
    "故障": "incident",
    "审查": "review",
    "复盘": "review",
    "交接": "handoff",
    "工作流": "workflow",
    "定时": "cron",
    "内存": "memory",
    "记忆": "memory",
}


def parse_simple_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key = None
    current_list = None

    # Step 1: find baseline indentation of non-empty lines
    lines_with_indent = []
    min_indent = None
    for line in text.splitlines():
        # Strip comment first
        stripped_comment = line.split("#")[0]
        if not stripped_comment.strip():
            continue
        indent = len(stripped_comment) - len(stripped_comment.lstrip())
        if min_indent is None or indent < min_indent:
            min_indent = indent
        lines_with_indent.append((indent, stripped_comment.strip()))

    # Step 2: parse normalized lines
    for indent, stripped in lines_with_indent:
        actual_indent = max(0, indent - (min_indent or 0))

        if stripped.startswith("-") and current_key is not None:
            val = stripped[1:].strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            if current_list is not None:
                current_list.append(val)
            else:
                if not isinstance(result.get(current_key), list):
                    result[current_key] = []
                result[current_key].append(val)
            continue

        if ":" in stripped:
            parts = stripped.split(":", 1)
            k = parts[0].strip()
            v = parts[1].strip()

            if not v:
                if actual_indent == 0:
                    current_key = k
                    result[k] = {}
                    current_list = None
                elif actual_indent > 0 and current_key in result and isinstance(result[current_key], dict):
                    result[current_key][k] = []
                    current_list = result[current_key][k]
            else:
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                if v.lower() == "true":
                    val_parsed = True
                elif v.lower() == "false":
                    val_parsed = False
                else:
                    try:
                        val_parsed = int(v)
                    except ValueError:
                        try:
                            val_parsed = float(v)
                        except ValueError:
                            val_parsed = v

                if actual_indent == 0:
                    result[k] = val_parsed
                    current_key = None
                    current_list = None
                elif actual_indent > 0:
                    if current_key and isinstance(result[current_key], dict):
                        result[current_key][k] = val_parsed
                    else:
                        result[k] = val_parsed
    return result


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        content = config_path.read_text(encoding="utf-8")
        return parse_simple_yaml(content)
    except Exception:
        return {}


def get_tag_keywords(config: dict[str, Any]) -> set[str]:
    keywords = set(DEFAULT_TAG_KEYWORDS)
    cfg_keywords = config.get("tag_keywords")
    if isinstance(cfg_keywords, list):
        for kw in cfg_keywords:
            if isinstance(kw, str):
                keywords.add(kw.strip().lower())
    return keywords
