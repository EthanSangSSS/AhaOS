from __future__ import annotations

import re
import time
from collections import defaultdict
from hashlib import sha1

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

        # Dynamic novelty calculation
        projects_count = len(projects)
        evidence_count = len(evidence)
        ages = [current_time - atom.created_at for atom in group if atom.created_at > 0]
        avg_age = sum(ages) / len(ages) if ages else 0.0
        age_factor = min(0.2, avg_age * 0.00001)

        dists = []
        for idx1 in range(len(group)):
            for idx2 in range(idx1 + 1, len(group)):
                w1 = set(group[idx1].tags)
                w2 = set(group[idx2].tags)
                union = w1.union(w2)
                if union:
                    jaccard_dist = 1.0 - len(w1.intersection(w2)) / len(union)
                else:
                    jaccard_dist = 1.0
                dists.append(jaccard_dist)
        avg_struct_dist = sum(dists) / len(dists) if dists else 0.5

        novelty = 0.4 + 0.1 * min(projects_count, 3) + 0.05 * min(evidence_count, 4) + age_factor + 0.1 * avg_struct_dist
        novelty = min(1.0, max(0.1, novelty))

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

            # Dynamic novelty calculation
            evidence_count = len(evidence)
            age = current_time - old.created_at if old.created_at > 0 else 0.0
            age_factor = min(0.2, age * 0.00001)

            dists = []
            for idx1 in range(len(group)):
                for idx2 in range(idx1 + 1, len(group)):
                    w1 = set(group[idx1].tags)
                    w2 = set(group[idx2].tags)
                    union = w1.union(w2)
                    if union:
                        jaccard_dist = 1.0 - len(w1.intersection(w2)) / len(union)
                    else:
                        jaccard_dist = 1.0
                    dists.append(jaccard_dist)
            avg_struct_dist = sum(dists) / len(dists) if dists else 0.5

            novelty = 0.4 + 0.05 * min(evidence_count, 4) + age_factor + 0.1 * avg_struct_dist
            novelty = min(1.0, max(0.1, novelty))

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
                    recommended_action=(
                        "Run a latest-state check using repository telemetry, PR diffs, logs, or source files, then deprecate stale memory explicitly."
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

        # Dynamic novelty calculation
        evidence_count = len(atom.evidence)
        age = current_time - atom.created_at if atom.created_at > 0 else 0.0
        age_factor = min(0.2, age * 0.00001)

        dists = []
        w1 = set(atom.tags)
        for other in atoms:
            if other.id == atom.id:
                continue
            w2 = set(other.tags)
            union = w1.union(w2)
            if union:
                jaccard_dist = 1.0 - len(w1.intersection(w2)) / len(union)
            else:
                jaccard_dist = 1.0
            dists.append(jaccard_dist)
        avg_struct_dist = sum(dists) / len(dists) if dists else 0.5

        novelty = 0.3 + 0.1 * min(evidence_count, 4) + age_factor + 0.2 * avg_struct_dist
        novelty = min(1.0, max(0.1, novelty))

        claim = (
            f"The procedure or decision `{atom.claim}` has high salience and may be worth packaging as a reusable agent skill or checklist."
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
                recommended_action="Convert this into a small `SKILL.md`, checklist, or repo-level SOP if it recurs once more.",
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

        # Dynamic novelty calculation
        evidence_count = len(evidence)
        age = current_time - loop.created_at if loop.created_at > 0 else 0.0
        age_factor = min(0.2, age * 0.00001)

        # Structural distance
        loop_tags = _extract_tags(loop.title + " " + loop.why_it_matters)
        dists = []
        for atom in related:
            w2 = set(atom.tags)
            union = loop_tags.union(w2)
            if union:
                jaccard_dist = 1.0 - len(loop_tags.intersection(w2)) / len(union)
            else:
                jaccard_dist = 1.0
            dists.append(jaccard_dist)
        avg_struct_dist = sum(dists) / len(dists) if dists else 0.5

        novelty = 0.35 + 0.05 * min(evidence_count, 4) + age_factor + 0.15 * avg_struct_dist
        novelty = min(1.0, max(0.1, novelty))

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
                recommended_action="Define one small action, one validation command, and one stop condition for this loop.",
            )
        )
    return candidates


def mine_negative_space(
    atoms: list[MemoryAtom], current_time: float | None = None
) -> list[InsightCandidate]:
    if current_time is None:
        current_time = time.time()

    # 1. Group active atoms by tag
    by_tag: dict[str, list[MemoryAtom]] = defaultdict(list)
    for atom in atoms:
        if atom.status == "active":
            for tag in atom.tags:
                by_tag[tag].append(atom)

    candidates: list[InsightCandidate] = []
    for tag, group in by_tag.items():
        if len(group) < 2:
            continue

        # Check if there is any procedural or decision solution containing this tag
        has_solution = any(atom.type in {"procedural", "decision"} for atom in group)
        if has_solution:
            continue

        evidence = _merge_evidence(group)
        # Compute novelty based on projects count, evidence count, age, structural distance
        projects = sorted({atom.project for atom in group})
        projects_count = len(projects)

        ages = [current_time - atom.created_at for atom in group if atom.created_at > 0]
        avg_age = sum(ages) / len(ages) if ages else 0.0
        age_factor = min(0.2, avg_age * 0.00001)

        dists = []
        for idx1 in range(len(group)):
            for idx2 in range(idx1 + 1, len(group)):
                w1 = set(group[idx1].tags)
                w2 = set(group[idx2].tags)
                union = w1.union(w2)
                if union:
                    jaccard_dist = 1.0 - len(w1.intersection(w2)) / len(union)
                else:
                    jaccard_dist = 1.0
                dists.append(jaccard_dist)
        avg_struct_dist = sum(dists) / len(dists) if dists else 0.5

        novelty = 0.5 + 0.05 * min(projects_count, 3) + 0.05 * min(len(evidence), 4) + age_factor + 0.1 * avg_struct_dist
        novelty = min(1.0, max(0.1, novelty))

        title = f"Missing procedural solution for `{tag}`"
        claim = f"Multiple active memories ({len(group)}) reference `{tag}`, but no procedural or decision guidance exists for this topic."

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
                recommended_action=f"Define a step-by-step procedure or a decision rule for managing `{tag}`.",
            )
        )
    return candidates


def incubate(
    atoms: list[MemoryAtom], loops: list[OpenLoop], current_time: float | None = None
) -> list[InsightCandidate]:
    if current_time is None:
        current_time = time.time()

    candidates: list[InsightCandidate] = []
    candidates.extend(mine_cross_project_patterns(atoms, current_time))
    candidates.extend(mine_contradictions(atoms, current_time))
    candidates.extend(mine_reuse_opportunities(atoms, current_time))
    candidates.extend(mine_open_loop_pressure(loops, atoms, current_time))
    candidates.extend(mine_negative_space(atoms, current_time))

    unique: dict[str, InsightCandidate] = {}
    for candidate in candidates:
        unique[candidate.id] = candidate

    return sorted(unique.values(), key=lambda candidate: candidate.score, reverse=True)
