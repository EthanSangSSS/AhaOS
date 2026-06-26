from __future__ import annotations

import time

from .models import MemoryAtom, OpenLoop


PRIORITY_WEIGHT = {
    "P0": 1.0,
    "P1": 0.8,
    "P2": 0.55,
    "P3": 0.3,
}


def memory_pressure(atom: MemoryAtom, current_time: float | None = None) -> float:
    type_weight = {
        "failure": 0.95,
        "open_loop": 0.9,
        "decision": 0.75,
        "procedural": 0.7,
        "episodic": 0.5,
        "semantic": 0.45,
    }.get(atom.type, 0.45)

    evidence_bonus = min(len(atom.evidence) * 0.08, 0.24)
    base = 0.4 * atom.salience + 0.25 * atom.confidence + 0.25 * type_weight + evidence_bonus

    age_boost = 0.0
    if atom.created_at > 0.0:
        if current_time is None:
            current_time = time.time()
        age = max(0.0, current_time - atom.created_at)
        age_boost = min(0.2, age * 0.00001)

    return min(1.0, base + age_boost)


def loop_pressure(loop: OpenLoop, current_time: float | None = None) -> float:
    base = PRIORITY_WEIGHT.get(loop.priority, 0.55)

    age_boost = 0.0
    if loop.created_at > 0.0:
        if current_time is None:
            current_time = time.time()
        age = max(0.0, current_time - loop.created_at)
        age_boost = min(0.2, age * 0.00001)

    return min(1.0, base + age_boost)


def select_high_pressure_atoms(
    atoms: list[MemoryAtom], threshold: float = 0.55, current_time: float | None = None
) -> list[MemoryAtom]:
    return [atom for atom in atoms if memory_pressure(atom, current_time=current_time) >= threshold]
