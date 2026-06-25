from __future__ import annotations

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


def mine_cross_project_patterns(atoms: list[MemoryAtom]) -> list[InsightCandidate]:
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
                novelty=0.68,
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


def mine_contradictions(atoms: list[MemoryAtom]) -> list[InsightCandidate]:
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
            evidence = _merge_evidence([old, *active])
            if len(evidence) < 2:
                continue
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
                    novelty=0.62,
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


def mine_reuse_opportunities(atoms: list[MemoryAtom]) -> list[InsightCandidate]:
    procedural = [atom for atom in atoms if atom.type in {"procedural", "decision"}]
    candidates: list[InsightCandidate] = []
    for atom in procedural:
        if memory_pressure(atom) < 0.65:
            continue
        if not atom.evidence:
            continue
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
                novelty=0.55,
                usefulness=0.75,
                actionability=0.83,
                evidence_strength=min(1.0, len(atom.evidence) / 3),
                risk=0.2,
                recommended_action="Convert this into a small `SKILL.md`, checklist, or repo-level SOP if it recurs once more.",
            )
        )
    return candidates


def mine_open_loop_pressure(loops: list[OpenLoop], atoms: list[MemoryAtom]) -> list[InsightCandidate]:
    candidates: list[InsightCandidate] = []
    atoms_by_id = {atom.id: atom for atom in atoms}
    for loop in loops:
        if loop_pressure(loop) < 0.75:
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
        claim = f"The open loop `{loop.title}` has high pressure and should be converted into a bounded next action."
        candidates.append(
            InsightCandidate(
                id=_stable_id("ins", claim),
                title=f"High-pressure open loop: {loop.title}",
                claim=claim,
                evidence=evidence,
                mechanism="open_loop_pressure",
                novelty=0.5,
                usefulness=0.84,
                actionability=0.88,
                evidence_strength=min(1.0, len(evidence) / 3),
                risk=0.16,
                recommended_action="Define one small action, one validation command, and one stop condition for this loop.",
            )
        )
    return candidates


def incubate(atoms: list[MemoryAtom], loops: list[OpenLoop]) -> list[InsightCandidate]:
    candidates: list[InsightCandidate] = []
    candidates.extend(mine_cross_project_patterns(atoms))
    candidates.extend(mine_contradictions(atoms))
    candidates.extend(mine_reuse_opportunities(atoms))
    candidates.extend(mine_open_loop_pressure(loops, atoms))

    unique: dict[str, InsightCandidate] = {}
    for candidate in candidates:
        unique[candidate.id] = candidate

    return sorted(unique.values(), key=lambda candidate: candidate.score, reverse=True)
