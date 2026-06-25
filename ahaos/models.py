from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


MemoryType = Literal[
    "semantic",
    "episodic",
    "procedural",
    "decision",
    "failure",
    "open_loop",
]

TrustLevel = Literal[
    "verified_telemetry",
    "first_party_file",
    "user_statement",
    "model_inference",
    "untrusted_external",
]

InsightMechanism = Literal[
    "cross_project_pattern",
    "contradiction",
    "reuse_opportunity",
    "open_loop_pressure",
    "negative_space",
]


@dataclass(frozen=True)
class Evidence:
    type: str
    ref: str
    quote: str | None = None
    trust_level: TrustLevel = "user_statement"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Evidence":
        return cls(
            type=str(data.get("type", "unknown")),
            ref=str(data.get("ref", "")),
            quote=data.get("quote"),
            trust_level=data.get("trust_level", "user_statement"),
        )


@dataclass(frozen=True)
class MemoryAtom:
    id: str
    claim: str
    type: MemoryType = "semantic"
    project: str = "unknown"
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float = 0.5
    salience: float = 0.5
    tags: list[str] = field(default_factory=list)
    status: str = "active"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryAtom":
        return cls(
            id=str(data["id"]),
            claim=str(data["claim"]),
            type=data.get("type", "semantic"),
            project=str(data.get("project", "unknown")),
            evidence=[Evidence.from_dict(x) for x in data.get("evidence", [])],
            confidence=float(data.get("confidence", 0.5)),
            salience=float(data.get("salience", 0.5)),
            tags=[str(x) for x in data.get("tags", [])],
            status=str(data.get("status", "active")),
        )


@dataclass(frozen=True)
class OpenLoop:
    id: str
    title: str
    why_it_matters: str
    project: str = "unknown"
    priority: str = "P2"
    status: str = "open"
    related_memories: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpenLoop":
        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            why_it_matters=str(data.get("why_it_matters", "")),
            project=str(data.get("project", "unknown")),
            priority=str(data.get("priority", "P2")),
            status=str(data.get("status", "open")),
            related_memories=[str(x) for x in data.get("related_memories", [])],
        )


@dataclass(frozen=True)
class InsightCandidate:
    id: str
    title: str
    claim: str
    evidence: list[Evidence]
    mechanism: InsightMechanism
    novelty: float
    usefulness: float
    actionability: float
    evidence_strength: float
    risk: float
    recommended_action: str
    do_not_do: str = "Do not execute state-changing actions based only on this insight."

    @property
    def score(self) -> float:
        return (
            0.22 * self.novelty
            + 0.28 * self.usefulness
            + 0.22 * self.actionability
            + 0.20 * self.evidence_strength
            - 0.18 * self.risk
        )
