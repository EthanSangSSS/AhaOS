from __future__ import annotations

from .models import MemoryAtom, OpenLoop


PRIORITY_WEIGHT = {
    "P0": 1.0,
    "P1": 0.8,
    "P2": 0.55,
    "P3": 0.3,
}


def memory_pressure(atom: MemoryAtom) -> float:
    type_weight = {
        "failure": 0.95,
        "open_loop": 0.9,
        "decision": 0.75,
        "procedural": 0.7,
        "episodic": 0.5,
        "semantic": 0.45,
    }.get(atom.type, 0.45)

    evidence_bonus = min(len(atom.evidence) * 0.08, 0.24)
    return min(1.0, 0.4 * atom.salience + 0.25 * atom.confidence + 0.25 * type_weight + evidence_bonus)


def loop_pressure(loop: OpenLoop) -> float:
    return PRIORITY_WEIGHT.get(loop.priority, 0.55)


def select_high_pressure_atoms(atoms: list[MemoryAtom], threshold: float = 0.55) -> list[MemoryAtom]:
    return [atom for atom in atoms if memory_pressure(atom) >= threshold]
