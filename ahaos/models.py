from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
    "spreading_activation",
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


def _timestamp(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
        try:
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            return default
    return default


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
    created_at: float = 0.0
    last_seen_at: float = 0.0
    last_triggered_at: float = 0.0
    activation_count: int = 0

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
            created_at=_timestamp(data.get("created_at")),
            last_seen_at=_timestamp(data.get("last_seen_at")),
            last_triggered_at=_timestamp(data.get("last_triggered_at")),
            activation_count=int(data.get("activation_count", 0)),
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
    created_at: float = 0.0
    last_seen_at: float = 0.0
    last_triggered_at: float = 0.0
    activation_count: int = 0

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
            created_at=_timestamp(data.get("created_at")),
            last_seen_at=_timestamp(data.get("last_seen_at")),
            last_triggered_at=_timestamp(data.get("last_triggered_at")),
            activation_count=int(data.get("activation_count", 0)),
        )


# Score formula weights — kept here so they are easy to tune together.
_W_NOVELTY = 0.20
_W_USEFULNESS = 0.25
_W_ACTIONABILITY = 0.20
_W_EVIDENCE = 0.18
_W_SURPRISE = 0.10   # unexpectedness: high structural distance, low surface similarity
_W_RELEVANCE = 0.05  # relevance to current open loops
_W_RISK = -0.18


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
    # P2-A: surprise = unexpectedness of the connection (structural distance × inverse lexical overlap).
    # Distinct from novelty: novelty measures project/evidence breadth; surprise measures
    # how unlikely the connection looks on the surface yet how structurally isomorphic it is.
    surprise: float = 0.0
    # P2-A: relevance to currently open loops / high-pressure atoms.
    relevance: float = 0.0
    # P3-C: activation_count / seen_count representing maturation or trigger frequency
    activation_count: int = 0

    @property
    def score(self) -> float:
        import math

        base = (
            _W_NOVELTY * self.novelty
            + _W_USEFULNESS * self.usefulness
            + _W_ACTIONABILITY * self.actionability
            + _W_EVIDENCE * self.evidence_strength
            + _W_SURPRISE * self.surprise
            + _W_RELEVANCE * self.relevance
            + _W_RISK * self.risk
        )
        boost = 0.05 * math.log(1 + self.activation_count) if self.activation_count > 0 else 0.0
        return round(base + boost, 4)
