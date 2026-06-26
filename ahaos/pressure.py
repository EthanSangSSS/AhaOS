from __future__ import annotations

import math
import time

from .models import MemoryAtom, OpenLoop


PRIORITY_WEIGHT = {
    "P0": 1.0,
    "P1": 0.8,
    "P2": 0.55,
    "P3": 0.3,
}

# P1-A: Ebbinghaus forgetting curve parameters.
# Half-life in seconds: ~30 days → an atom unseen for 30 days retains 50 % of its salience.
_FORGETTING_HALF_LIFE = 30 * 24 * 3600  # 2_592_000 s
_FORGETTING_FLOOR = 0.3                 # salience never decays below this floor


def salience_with_decay(atom: MemoryAtom, current_time: float) -> float:
    """
    Return effective salience after applying the Ebbinghaus forgetting curve.

    If neither ``last_seen_at`` nor ``created_at`` is available (both ≤ 0)
    the raw salience is returned unchanged.
    When an atom is re-triggered its ``last_seen_at`` resets, so effective
    salience snaps back toward the base value on the next run — modelling the
    'pop' of a dormant memory being re-discovered.
    """
    base = atom.salience
    # Prefer last_seen_at; fall back to created_at; if neither is set skip decay
    if atom.last_seen_at > 0:
        reference = atom.last_seen_at
    elif atom.created_at > 0:
        reference = atom.created_at
    else:
        return base  # no temporal anchor → no decay
    elapsed = max(0.0, current_time - reference)
    decay = 0.5 ** (elapsed / _FORGETTING_HALF_LIFE)
    return max(_FORGETTING_FLOOR, base * decay)


def activation_heat(atom: MemoryAtom) -> float:
    """
    A small bonus [0, 0.15] for atoms that have been triggered multiple times.
    Models the idea that repeated weak re-activations lower the threshold for
    the next aha moment.  Growth is logarithmic so a single trigger is still
    meaningful without runaway inflation.
    """
    if atom.activation_count <= 0:
        return 0.0
    return min(0.15, 0.05 * math.log1p(atom.activation_count))


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

    if current_time is None:
        current_time = time.time()

    # P1-A: use decayed salience instead of raw salience
    effective_salience = salience_with_decay(atom, current_time)

    base = (
        0.4 * effective_salience
        + 0.25 * atom.confidence
        + 0.25 * type_weight
        + evidence_bonus
    )

    age_boost = 0.0
    if atom.created_at > 0.0:
        age = max(0.0, current_time - atom.created_at)
        age_boost = min(0.2, age * 0.00001)

    # P1-A: activation heat from repeated triggers
    heat = activation_heat(atom)

    return min(1.0, base + age_boost + heat)


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
