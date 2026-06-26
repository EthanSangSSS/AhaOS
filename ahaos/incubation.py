from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from dataclasses import replace
from hashlib import sha1
from typing import Any

from .models import Evidence, InsightCandidate, MemoryAtom, OpenLoop
from .pressure import loop_pressure, memory_pressure


def _stable_id(prefix: str, text: str) -> str:
    return f"{prefix}_{sha1(text.encode('utf-8')).hexdigest()[:12]}"


def _merge_evidence(atoms: list[MemoryAtom]) -> list[Evidence]:
    evidence: list[Evidence] = []
    seen: set[tuple[str, str]] = set()
    for atom in atoms:
        for item in atom.evidence:
            key = (item.type, item.ref)
            if key not in seen:
                seen.add(key)
                evidence.append(item)
    return evidence


def _extract_tags(text: str) -> set[str]:
    tags = set()
    for tag in re.findall(r"#([A-Za-z0-9_-]+)", text):
        tags.add(tag.lower())
    for tag in re.findall(r"`([A-Za-z0-9_-]+)`", text):
        tags.add(tag.lower())
    return tags


def _jaccard_tag_distance(a: MemoryAtom, b: MemoryAtom) -> float:
    """Tag-space Jaccard *distance* (1 = fully disjoint, 0 = identical)."""
    ta, tb = set(a.tags), set(b.tags)
    union = ta | tb
    if not union:
        return 1.0
    return 1.0 - len(ta & tb) / len(union)


def _compute_surprise(group: list[MemoryAtom], structural_dist: float | None = None) -> float:
    """
    P2-A: Surprise = unexpectedness of the connection.

    High surprise  → atoms are structurally similar but lexically distant.
    Low surprise   → atoms are close in both tag space and surface text.

    Formula: mean pairwise tag-Jaccard distance, optionally blended with
    the structural_echo slot distance when available.
    """
    if len(group) < 2:
        return 0.0
    dists = [
        _jaccard_tag_distance(group[i], group[j])
        for i in range(len(group))
        for j in range(i + 1, len(group))
    ]
    tag_dist = sum(dists) / len(dists)
    if structural_dist is not None:
        # 50/50 blend with the structural slot distance
        return round(min(1.0, 0.5 * tag_dist + 0.5 * structural_dist), 3)
    return round(min(1.0, tag_dist), 3)


def _compute_novelty(
    projects_count: int,
    evidence_count: int,
    avg_age: float,
    avg_struct_dist: float,
    base: float = 0.4,
) -> float:
    age_factor = min(0.2, avg_age * 0.00001)
    raw = base + 0.1 * min(projects_count, 3) + 0.05 * min(evidence_count, 4) + age_factor + 0.1 * avg_struct_dist
    return round(min(1.0, max(0.1, raw)), 3)


# ---------------------------------------------------------------------------
# P1-B: Spreading-activation helpers
# ---------------------------------------------------------------------------

def _build_tag_graph(atoms: list[MemoryAtom]) -> dict[str, set[str]]:
    """
    Build an undirected atom graph.  Two atoms are neighbours when their
    shared tag count ≥ 1 and their tag Jaccard *similarity* ≥ 0.15.
    This is intentionally loose — we want weak connections to propagate.
    """
    graph: dict[str, set[str]] = defaultdict(set)
    for i, a in enumerate(atoms):
        for b in atoms[i + 1:]:
            ta, tb = set(a.tags), set(b.tags)
            union = ta | tb
            if union and len(ta & tb) / len(union) >= 0.15:
                graph[a.id].add(b.id)
                graph[b.id].add(a.id)
    return dict(graph)


def mine_spreading_activation(
    atoms: list[MemoryAtom],
    trigger_ids: set[str],
    hops: int = 2,
    current_time: float | None = None,
) -> list[InsightCandidate]:
    """
    P1-B: Spreading activation via BFS.

    Starting from ``trigger_ids``, propagate along the tag-similarity graph.
    Atoms reached only at hop ≥ 2 are "remote" — they were not directly
    associated with the trigger but became weakly activated through
    intermediate nodes.  These are the candidates most likely to produce
    genuine surprise.

    Conditions for a candidate to be emitted:
    - Reached at hop ≥ 2 (truly remote, not just a direct neighbour)
    - Has at least one piece of evidence (safety gate)
    - Has memory_pressure ≥ 0.45 (some base relevance)
    """
    if not trigger_ids:
        return []
    if current_time is None:
        current_time = time.time()

    graph = _build_tag_graph(atoms)
    atoms_by_id = {a.id: a for a in atoms}

    # BFS from all trigger nodes simultaneously
    visited: dict[str, int] = {tid: 0 for tid in trigger_ids if tid in graph}
    queue: deque[tuple[str, int]] = deque((tid, 0) for tid in trigger_ids if tid in graph)

    while queue:
        node, depth = queue.popleft()
        if depth >= hops:
            continue
        for neighbour in graph.get(node, set()):
            if neighbour not in visited:
                visited[neighbour] = depth + 1
                queue.append((neighbour, depth + 1))

    candidates: list[InsightCandidate] = []
    for atom_id, hop in visited.items():
        if hop < 2 or atom_id in trigger_ids:
            continue
        atom = atoms_by_id.get(atom_id)
        if not atom or not atom.evidence:
            continue
        if memory_pressure(atom, current_time) < 0.45:
            continue

        # Surprise: distance from the nearest trigger node
        nearest_trigger = min(
            (
                _jaccard_tag_distance(atoms_by_id[tid], atom)
                for tid in trigger_ids
                if tid in atoms_by_id
            ),
            default=1.0,
        )
        surprise = round(min(1.0, 0.3 + 0.35 * hop + 0.35 * nearest_trigger), 3)

        # Novelty increases with hop distance — the further, the more unexpected
        novelty = round(min(1.0, 0.35 + 0.15 * hop), 3)

        claim = (
            f"Memory `{atom.claim[:80]}` was remotely activated after {hop} hops "
            "from new inputs, suggesting latent relevance not captured by direct tags."
        )
        candidates.append(
            InsightCandidate(
                id=_stable_id("ins", claim),
                title=f"Remote activation ({hop}-hop): {atom.claim[:50]}",
                claim=claim,
                evidence=atom.evidence,
                mechanism="spreading_activation",
                novelty=novelty,
                usefulness=0.70,
                actionability=0.60,
                evidence_strength=min(1.0, len(atom.evidence) / 3),
                risk=0.25,
                surprise=surprise,
                relevance=0.5,
                activation_count=atom.activation_count,
                recommended_action=(
                    f"Investigate whether `{atom.claim[:80]}` is relevant to the "
                    "newly added inputs and, if so, create an explicit link."
                ),
            )
        )
    return candidates


# ---------------------------------------------------------------------------
# Core miners (P2-A surprise scores wired in)
# ---------------------------------------------------------------------------

def mine_cross_project_patterns(
    atoms: list[MemoryAtom], current_time: float | None = None
) -> list[InsightCandidate]:
    if current_time is None:
        current_time = time.time()

    by_tag: dict[str, list[MemoryAtom]] = defaultdict(list)
    for atom in atoms:
        for tag in atom.tags:
            by_tag[tag].append(atom)

    candidates: list[InsightCandidate] = []
    for tag, group in by_tag.items():
        projects = sorted({atom.project for atom in group})
        if len(projects) < 2:
            continue
        evidence = _merge_evidence(group)
        if len(evidence) < 2:
            continue

        ages = [current_time - atom.created_at for atom in group if atom.created_at > 0]
        avg_age = sum(ages) / len(ages) if ages else 0.0
        dists = [
            _jaccard_tag_distance(group[i], group[j])
            for i in range(len(group))
            for j in range(i + 1, len(group))
        ]
        avg_struct_dist = sum(dists) / len(dists) if dists else 0.5
        novelty = _compute_novelty(len(projects), len(evidence), avg_age, avg_struct_dist)
        surprise = _compute_surprise(group)

        title = f"Repeated pattern detected around `{tag}`"
        claim = (
            f"The tag `{tag}` appears across {len(projects)} projects "
            f"({', '.join(projects)}), suggesting a reusable pattern rather than isolated work."
        )
        candidates.append(
            InsightCandidate(
                id=_stable_id("ins", claim),
                title=title,
                claim=claim,
                evidence=evidence,
                mechanism="cross_project_pattern",
                novelty=novelty,
                usefulness=0.82,
                actionability=0.74,
                evidence_strength=min(1.0, len(evidence) / 4),
                risk=0.22,
                surprise=surprise,
                activation_count=max((atom.activation_count for atom in group), default=0),
                recommended_action=(
                    f"Extract a reusable checklist, module, or playbook for `{tag}` before the next similar task."
                ),
            )
        )
    return candidates


def mine_contradictions(
    atoms: list[MemoryAtom], current_time: float | None = None
) -> list[InsightCandidate]:
    if current_time is None:
        current_time = time.time()

    candidates: list[InsightCandidate] = []
    superseded = [atom for atom in atoms if atom.status == "superseded"]
    active_by_tag: dict[str, list[MemoryAtom]] = defaultdict(list)
    for atom in atoms:
        if atom.status == "active":
            for tag in atom.tags:
                active_by_tag[tag].append(atom)

    for old in superseded:
        for tag in old.tags:
            active = active_by_tag.get(tag, [])
            if not active:
                continue
            group = [old, *active]
            evidence = _merge_evidence(group)
            if len(evidence) < 2:
                continue

            age = current_time - old.created_at if old.created_at > 0 else 0.0
            dists = [
                _jaccard_tag_distance(group[i], group[j])
                for i in range(len(group))
                for j in range(i + 1, len(group))
            ]
            avg_struct_dist = sum(dists) / len(dists) if dists else 0.5
            novelty = _compute_novelty(1, len(evidence), age, avg_struct_dist, base=0.4)
            surprise = _compute_surprise(group)

            claim = (
                f"A prior memory around `{tag}` is marked superseded while active memories still use the same tag. "
                "The agent should resolve the latest verified state before relying on this area."
            )
            candidates.append(
                InsightCandidate(
                    id=_stable_id("ins", claim),
                    title=f"Potential outdated memory around `{tag}`",
                    claim=claim,
                    evidence=evidence,
                    mechanism="contradiction",
                    novelty=novelty,
                    usefulness=0.78,
                    actionability=0.8,
                    evidence_strength=min(1.0, len(evidence) / 4),
                    risk=0.18,
                    surprise=surprise,
                    activation_count=max((atom.activation_count for atom in group), default=0),
                    recommended_action=(
                        "Run a latest-state check using repository telemetry, PR diffs, logs, or source files, "
                        "then deprecate stale memory explicitly."
                    ),
                )
            )
    return candidates


def mine_reuse_opportunities(
    atoms: list[MemoryAtom], current_time: float | None = None
) -> list[InsightCandidate]:
    if current_time is None:
        current_time = time.time()

    procedural = [atom for atom in atoms if atom.type in {"procedural", "decision"}]
    candidates: list[InsightCandidate] = []
    for atom in procedural:
        if memory_pressure(atom, current_time=current_time) < 0.65:
            continue
        if not atom.evidence:
            continue

        age = current_time - atom.created_at if atom.created_at > 0 else 0.0
        dists = [_jaccard_tag_distance(atom, other) for other in atoms if other.id != atom.id]
        avg_struct_dist = sum(dists) / len(dists) if dists else 0.5
        novelty = _compute_novelty(1, len(atom.evidence), age, avg_struct_dist, base=0.3)
        surprise = round(min(1.0, avg_struct_dist), 3)  # standalone atom surprise

        claim = (
            f"The procedure or decision `{atom.claim}` has high salience and may be worth "
            "packaging as a reusable agent skill or checklist."
        )
        candidates.append(
            InsightCandidate(
                id=_stable_id("ins", claim),
                title="Possible reusable agent asset",
                claim=claim,
                evidence=atom.evidence,
                mechanism="reuse_opportunity",
                novelty=novelty,
                usefulness=0.75,
                actionability=0.83,
                evidence_strength=min(1.0, len(atom.evidence) / 3),
                risk=0.2,
                surprise=surprise,
                activation_count=atom.activation_count,
                recommended_action=(
                    "Convert this into a small `SKILL.md`, checklist, or repo-level SOP if it recurs once more."
                ),
            )
        )
    return candidates


def mine_open_loop_pressure(
    loops: list[OpenLoop], atoms: list[MemoryAtom], current_time: float | None = None
) -> list[InsightCandidate]:
    if current_time is None:
        current_time = time.time()

    candidates: list[InsightCandidate] = []
    atoms_by_id = {atom.id: atom for atom in atoms}
    for loop in loops:
        if loop_pressure(loop, current_time=current_time) < 0.75:
            continue
        related = [atoms_by_id[mem_id] for mem_id in loop.related_memories if mem_id in atoms_by_id]
        evidence = _merge_evidence(related)
        if not evidence:
            evidence = [
                Evidence(
                    type="open_loop",
                    ref=loop.id,
                    quote=loop.why_it_matters,
                    trust_level="user_statement",
                )
            ]

        age = current_time - loop.created_at if loop.created_at > 0 else 0.0
        loop_tags = _extract_tags(loop.title + " " + loop.why_it_matters)
        dists = []
        for atom in related:
            ta = set(atom.tags)
            union = loop_tags | ta
            if union:
                dists.append(1.0 - len(loop_tags & ta) / len(union))
            else:
                dists.append(1.0)
        avg_struct_dist = sum(dists) / len(dists) if dists else 0.5
        novelty = _compute_novelty(1, len(evidence), age, avg_struct_dist, base=0.35)
        surprise = round(min(1.0, avg_struct_dist), 3)

        claim = f"The open loop `{loop.title}` has high pressure and should be converted into a bounded next action."
        candidates.append(
            InsightCandidate(
                id=_stable_id("ins", claim),
                title=f"High-pressure open loop: {loop.title}",
                claim=claim,
                evidence=evidence,
                mechanism="open_loop_pressure",
                novelty=novelty,
                usefulness=0.84,
                actionability=0.88,
                evidence_strength=min(1.0, len(evidence) / 3),
                risk=0.16,
                surprise=surprise,
                activation_count=max([loop.activation_count] + [atom.activation_count for atom in related], default=0),
                recommended_action=(
                    "Define one small action, one validation command, and one stop condition for this loop."
                ),
            )
        )
    return candidates


def mine_negative_space(
    atoms: list[MemoryAtom], current_time: float | None = None
) -> list[InsightCandidate]:
    if current_time is None:
        current_time = time.time()

    by_tag: dict[str, list[MemoryAtom]] = defaultdict(list)
    for atom in atoms:
        if atom.status == "active":
            for tag in atom.tags:
                by_tag[tag].append(atom)

    candidates: list[InsightCandidate] = []
    for tag, group in by_tag.items():
        if len(group) < 2:
            continue
        if any(atom.type in {"procedural", "decision"} for atom in group):
            continue

        evidence = _merge_evidence(group)
        projects = sorted({atom.project for atom in group})
        ages = [current_time - atom.created_at for atom in group if atom.created_at > 0]
        avg_age = sum(ages) / len(ages) if ages else 0.0
        dists = [
            _jaccard_tag_distance(group[i], group[j])
            for i in range(len(group))
            for j in range(i + 1, len(group))
        ]
        avg_struct_dist = sum(dists) / len(dists) if dists else 0.5
        novelty = _compute_novelty(len(projects), len(evidence), avg_age, avg_struct_dist, base=0.5)
        surprise = _compute_surprise(group)

        title = f"Missing procedural solution for `{tag}`"
        claim = (
            f"Multiple active memories ({len(group)}) reference `{tag}`, "
            "but no procedural or decision guidance exists for this topic."
        )
        candidates.append(
            InsightCandidate(
                id=_stable_id("ins", claim),
                title=title,
                claim=claim,
                evidence=evidence,
                mechanism="negative_space",
                novelty=novelty,
                usefulness=0.7,
                actionability=0.75,
                evidence_strength=min(1.0, len(evidence) / 3),
                risk=0.15,
                surprise=surprise,
                activation_count=max((atom.activation_count for atom in group), default=0),
                recommended_action=f"Define a step-by-step procedure or a decision rule for managing `{tag}`.",
            )
        )
    return candidates


# ---------------------------------------------------------------------------
# P2-B: Candidate maturation (multi-cycle promotion)
# ---------------------------------------------------------------------------

def promote_matured_candidates(
    candidates: list[InsightCandidate],
    history: dict[str, Any],
) -> list[InsightCandidate]:
    """
    P2-B: Candidates that have surfaced ≥ 3 times receive a small usefulness
    boost, modelling the cognitive phenomenon where repeated weak re-activations
    lower the threshold until the insight breaks through to consciousness.

    ``history`` is keyed by candidate id, value must have ``seen_count``.
    Max boost = 0.15 (logarithmic growth to avoid runaway inflation).
    """
    result: list[InsightCandidate] = []
    for c in candidates:
        h = history.get(c.id, {})
        count = int(h.get("seen_count", 0))
        if count >= 3:
            boost = min(0.15, 0.05 * (count - 2))
            c = replace(c, usefulness=min(1.0, c.usefulness + boost))
        result.append(c)
    return result


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def incubate(
    atoms: list[MemoryAtom],
    loops: list[OpenLoop],
    current_time: float | None = None,
    trigger_ids: set[str] | None = None,
    candidate_history: dict[str, Any] | None = None,
) -> list[InsightCandidate]:
    if current_time is None:
        current_time = time.time()
    if trigger_ids is None:
        trigger_ids = set()
    if candidate_history is None:
        candidate_history = {}

    candidates: list[InsightCandidate] = []
    candidates.extend(mine_cross_project_patterns(atoms, current_time))
    candidates.extend(mine_contradictions(atoms, current_time))
    candidates.extend(mine_reuse_opportunities(atoms, current_time))
    candidates.extend(mine_open_loop_pressure(loops, atoms, current_time))
    candidates.extend(mine_negative_space(atoms, current_time))
    # P1-B: spreading activation only when we know which atoms are new triggers
    if trigger_ids:
        candidates.extend(mine_spreading_activation(atoms, trigger_ids, hops=2, current_time=current_time))

    # Deduplicate (last writer wins — spreading activation may overlap with other miners)
    unique: dict[str, InsightCandidate] = {}
    for c in candidates:
        unique[c.id] = c

    # P2-B: maturation boost
    matured = promote_matured_candidates(list(unique.values()), candidate_history)

    return sorted(matured, key=lambda c: c.score, reverse=True)
