from __future__ import annotations

import pytest
from ahaos.models import MemoryAtom, OpenLoop
from ahaos.pressure import (
    salience_with_decay,
    activation_heat,
    memory_pressure,
    loop_pressure,
    _FORGETTING_HALF_LIFE,
    _FORGETTING_FLOOR,
)


def test_old_salience_decays() -> None:
    # Set up an atom seen one half-life ago
    atom_decayed = MemoryAtom(
        id="decayed",
        claim="Decayed claim",
        salience=0.8,
        created_at=1.0,
        last_seen_at=1.0,
    )
    
    # After one half-life, salience should decay to exactly 0.4 (50% of 0.8)
    decayed_val = salience_with_decay(atom_decayed, current_time=_FORGETTING_HALF_LIFE + 1.0)
    assert 0.38 < decayed_val < 0.42
    
    # An atom seen a very long time ago should decay to the floor (0.3)
    very_old_atom = MemoryAtom(
        id="very_old",
        claim="Very old claim",
        salience=0.8,
        created_at=1.0,
        last_seen_at=1.0,
    )
    floor_val = salience_with_decay(very_old_atom, current_time=_FORGETTING_HALF_LIFE * 50)
    assert floor_val == _FORGETTING_FLOOR


def test_activation_count_increases_pressure() -> None:
    # High activation count should increase the activation heat
    atom_inactive = MemoryAtom(id="inactive", claim="Inactive claim", activation_count=0)
    atom_active = MemoryAtom(id="active", claim="Active claim", activation_count=10)
    
    heat_inactive = activation_heat(atom_inactive)
    heat_active = activation_heat(atom_active)
    
    assert heat_inactive == 0.0
    assert heat_active > heat_inactive
    assert heat_active <= 0.15  # cap of activation heat
    
    # Check that memory_pressure includes this activation heat boost
    atom_base = MemoryAtom(
        id="base",
        claim="Base claim",
        type="semantic",
        confidence=0.5,
        salience=0.5,
        activation_count=0,
        created_at=100.0,
        last_seen_at=100.0,
    )
    atom_boosted = MemoryAtom(
        id="boosted",
        claim="Boosted claim",
        type="semantic",
        confidence=0.5,
        salience=0.5,
        activation_count=100,
        created_at=100.0,
        last_seen_at=100.0,
    )
    
    pressure_base = memory_pressure(atom_base, current_time=100.0)
    pressure_boosted = memory_pressure(atom_boosted, current_time=100.0)
    
    assert pressure_boosted > pressure_base


def test_old_open_loops_receive_bounded_age_boost() -> None:
    # Priority weights: P0=1.0, P1=0.8, P2=0.55, P3=0.3
    # Bounded age boost is added but capped at priority limits
    loop_fresh = OpenLoop(
        id="fresh",
        title="Fresh loop",
        why_it_matters="matters",
        priority="P2",
        created_at=1000.0,
    )
    
    # Loop created long ago (1,000,000 seconds ago)
    loop_old = OpenLoop(
        id="old",
        title="Old loop",
        why_it_matters="matters",
        priority="P2",
        created_at=1000.0,
    )
    
    p_fresh = loop_pressure(loop_fresh, current_time=1000.0)
    p_old = loop_pressure(loop_old, current_time=1000.0 + 1000000.0)
    
    assert p_old > p_fresh
    assert p_old <= 1.0  # overall cap
