from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import InsightCandidate


def render_markdown_report(candidates: list[InsightCandidate], top_k: int = 3) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    selected = candidates[:top_k]

    lines: list[str] = [
        f"# AhaOS Insight Report",
        "",
        f"Generated: {now}",
        "",
        f"Delivered insights: {len(selected)}",
        "",
    ]

    if not selected:
        lines.extend(
            [
                "## No verified insights",
                "",
                "No candidate passed the evidence and safety gates.",
                "",
            ]
        )
        return "\n".join(lines)

    for idx, item in enumerate(selected, start=1):
        lines.extend(
            [
                f"## {idx}. {item.title}",
                "",
                f"**Mechanism:** `{item.mechanism}`",
                "",
                "### Claim",
                "",
                item.claim,
                "",
                "### Evidence",
                "",
            ]
        )
        for evidence in item.evidence:
            quote = f" — {evidence.quote}" if evidence.quote else ""
            lines.append(f"- `{evidence.trust_level}` `{evidence.type}`: {evidence.ref}{quote}")
        lines.extend(
            [
                "",
                "### Recommended action",
                "",
                item.recommended_action,
                "",
                "### Risk / boundary",
                "",
                f"- Risk score: `{item.risk:.2f}`",
                f"- Boundary: {item.do_not_do}",
                "",
                "### Scores",
                "",
                f"- Novelty: `{item.novelty:.2f}`",
                f"- Usefulness: `{item.usefulness:.2f}`",
                f"- Actionability: `{item.actionability:.2f}`",
                f"- Evidence strength: `{item.evidence_strength:.2f}`",
                f"- Final score: `{item.score:.2f}`",
                "",
            ]
        )

    return "\n".join(lines)


def write_report(report_dir: Path, content: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = report_dir / f"{stamp}.md"
    path.write_text(content, encoding="utf-8")
    return path
