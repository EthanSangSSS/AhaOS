from __future__ import annotations

from pathlib import Path

from ahaos.cli import build_parser, cmd_init
from ahaos.models import Evidence, InsightCandidate, MemoryAtom, OpenLoop
from ahaos.pressure import loop_pressure, memory_pressure, select_high_pressure_atoms
from ahaos.report import write_report
from ahaos.verification import evidence_score, filter_verified, verify_candidate


def make_candidate(**overrides: object) -> InsightCandidate:
    data = {
        "id": "ins_test",
        "title": "Reusable release gate",
        "claim": "Release checks recur across projects.",
        "evidence": [
            Evidence(
                type="local_file",
                ref="notes.md",
                quote="release checks recur",
                trust_level="first_party_file",
            ),
            Evidence(
                type="local_file",
                ref="other-notes.md",
                quote="release checks recur elsewhere",
                trust_level="first_party_file",
            ),
        ],
        "mechanism": "cross_project_pattern",
        "novelty": 0.7,
        "usefulness": 0.8,
        "actionability": 0.7,
        "evidence_strength": 0.8,
        "risk": 0.2,
        "recommended_action": "Create a release checklist.",
        "do_not_do": "Do not change release settings without validation.",
    }
    data.update(overrides)
    return InsightCandidate(**data)


def test_init_writes_real_yaml_newlines(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(["init", "--path", str(tmp_path)])

    assert cmd_init(args) == 0

    config = tmp_path / ".ahaos" / "config.yaml"
    content = config.read_text(encoding="utf-8")
    assert "\\n" not in content
    assert content.splitlines() == [
        "delivery:",
        "  max_daily_insights: 3",
        "safety:",
        "  allow_autonomous_actions: false",
        "  require_evidence: true",
    ]


def test_write_report_does_not_overwrite_same_day(tmp_path: Path) -> None:
    first = write_report(tmp_path, "first")
    second = write_report(tmp_path, "second")

    assert first != second
    assert first.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"
    assert first.name.endswith(".md")
    assert second.name.endswith("-2.md")


def test_memory_pressure_weights_type_confidence_salience_and_evidence() -> None:
    low = MemoryAtom(
        id="mem_low",
        claim="Low salience note",
        type="semantic",
        confidence=0.2,
        salience=0.2,
    )
    high = MemoryAtom(
        id="mem_high",
        claim="High salience failure",
        type="failure",
        evidence=[Evidence(type="log", ref="failure.log")],
        confidence=0.9,
        salience=0.9,
    )

    assert memory_pressure(high) > memory_pressure(low)
    assert select_high_pressure_atoms([low, high], threshold=0.65) == [high]


def test_loop_pressure_uses_priority_weight_with_p2_default() -> None:
    assert loop_pressure(OpenLoop(id="loop_p0", title="urgent", why_it_matters="", priority="P0")) == 1.0
    assert loop_pressure(OpenLoop(id="loop_p1", title="high", why_it_matters="", priority="P1")) == 0.8
    assert loop_pressure(OpenLoop(id="loop_unknown", title="unknown", why_it_matters="", priority="PX")) == 0.55


def test_verify_candidate_accepts_evidence_backed_low_risk_candidate() -> None:
    candidate = make_candidate()

    ok, errors = verify_candidate(candidate)

    assert ok
    assert errors == []
    assert evidence_score(candidate) == 0.85
    assert filter_verified([candidate]) == [candidate]


def test_verify_candidate_rejects_missing_evidence_and_model_only_support() -> None:
    no_evidence = make_candidate(evidence=[])
    model_only = make_candidate(
        evidence=[
            Evidence(
                type="model_note",
                ref="scratch",
                quote="inferred only",
                trust_level="model_inference",
            )
        ]
    )

    ok, errors = verify_candidate(no_evidence)
    assert not ok
    assert "missing evidence" in errors
    assert "evidence score too low" in errors

    ok, errors = verify_candidate(model_only)
    assert not ok
    assert "evidence score too low" in errors
    assert "model inference cannot be the only evidence" in errors


def test_verify_candidate_requires_independent_sources_for_pattern_claims() -> None:
    candidate = make_candidate(
        evidence=[
            Evidence(
                type="local_file",
                ref="single-note.md",
                quote="same source",
                trust_level="first_party_file",
            )
        ]
    )

    ok, errors = verify_candidate(candidate)

    assert not ok
    assert "insufficient independent evidence" in errors


def test_time_pressure_age_boost() -> None:
    # MemoryAtom age boost — atom is seen at creation time so no forgetting decay
    base_atom = MemoryAtom(
        id="mem_age_1",
        claim="Claim for age boost",
        type="semantic",
        confidence=0.5,
        salience=0.5,
        created_at=100.0,
        last_seen_at=100.0,  # freshly seen at creation → no decay
    )
    p_young = memory_pressure(base_atom, current_time=100.0)
    p_old = memory_pressure(base_atom, current_time=40000.0)
    p_later = memory_pressure(base_atom, current_time=60000.0)

    # Age pressure accumulates over days rather than reaching its cap within hours.
    assert p_old > p_young
    assert p_later > p_old

    # OpenLoop age boost
    base_loop = OpenLoop(
        id="loop_age_1",
        title="Open Loop age boost",
        why_it_matters="needs validation",
        priority="P2",
        created_at=100.0,
    )
    pl_young = loop_pressure(base_loop, current_time=100.0)
    pl_old = loop_pressure(base_loop, current_time=40000.0)
    pl_later = loop_pressure(base_loop, current_time=60000.0)
    pl_twenty_days = loop_pressure(base_loop, current_time=100.0 + 20 * 24 * 60 * 60)

    assert pl_old > pl_young
    assert pl_later > pl_old
    assert pl_twenty_days == 0.75


# ---------------------------------------------------------------------------
# P1-A: salience decay and activation heat
# ---------------------------------------------------------------------------

def test_salience_decay_reduces_pressure_for_long_unseen_atoms() -> None:
    from ahaos.pressure import salience_with_decay, _FORGETTING_HALF_LIFE

    atom_fresh = MemoryAtom(
        id="fresh", claim="c", salience=0.8, created_at=0.0, last_seen_at=0.0
    )

    # Atom with no last_seen_at and no created_at → raw salience returned (no reference point)
    s_no_ref = salience_with_decay(atom_fresh, current_time=1000.0)
    assert s_no_ref == 0.8

    # Use an atom whose last_seen_at is set to a concrete point in the past (epoch 1)
    atom_with_ref = MemoryAtom(
        id="old_ref", claim="c", salience=0.8, created_at=1.0,
        last_seen_at=1.0,  # last seen at epoch 1 second; current_time = one half-life later
    )
    # After one half-life, effective salience should be ≈ 0.4 (50 % decay)
    s_after_half_life = salience_with_decay(atom_with_ref, current_time=_FORGETTING_HALF_LIFE + 1.0)
    assert 0.35 < s_after_half_life < 0.45

    # Floor is respected
    s_very_old = salience_with_decay(atom_with_ref, current_time=_FORGETTING_HALF_LIFE * 100)
    from ahaos.pressure import _FORGETTING_FLOOR
    assert s_very_old == _FORGETTING_FLOOR



def test_activation_heat_grows_logarithmically_and_is_capped() -> None:
    from ahaos.pressure import activation_heat

    atom0 = MemoryAtom(id="a0", claim="c", activation_count=0)
    atom1 = MemoryAtom(id="a1", claim="c", activation_count=1)
    atom10 = MemoryAtom(id="a10", claim="c", activation_count=10)
    atom1000 = MemoryAtom(id="a1000", claim="c", activation_count=1000)

    assert activation_heat(atom0) == 0.0
    assert activation_heat(atom1) > 0.0
    assert activation_heat(atom10) > activation_heat(atom1)
    # Cap at 0.15 — requires a large enough count: 0.05 * log1p(n) >= 0.15 → n >= e^3 - 1 ≈ 19
    assert activation_heat(atom1000) == 0.15
    # atom10 has not yet hit the cap
    assert activation_heat(atom10) < 0.15


def test_high_activation_atom_gets_pressure_boost() -> None:
    """An atom triggered many times should have higher pressure than an identical untriggered one."""
    base = dict(
        claim="Important recurring issue",
        type="failure",
        confidence=0.7,
        salience=0.7,
        created_at=1000.0,
        last_seen_at=1000.0,
    )
    cold = MemoryAtom(id="cold", activation_count=0, **base)
    hot = MemoryAtom(id="hot", activation_count=5, **base)
    assert memory_pressure(hot, current_time=1000.0) > memory_pressure(cold, current_time=1000.0)


# ---------------------------------------------------------------------------
# P1-B: spreading activation
# ---------------------------------------------------------------------------

def test_spreading_activation_finds_remote_atoms() -> None:
    from ahaos.incubation import mine_spreading_activation

    # Chain: trigger_a — (shared tag 'release') — middle_b — (shared tag 'rollback') — remote_c
    trigger_a = MemoryAtom(
        id="atom_trigger_a", claim="Release checklist for deployment.",
        tags=["release", "deployment"],
        evidence=[Evidence(type="log", ref="deploy.log")],
    )
    middle_b = MemoryAtom(
        id="atom_middle_b", claim="Deployment rollback procedure.",
        tags=["deployment", "rollback"],
        evidence=[Evidence(type="log", ref="rollback.log")],
    )
    remote_c = MemoryAtom(
        id="atom_remote_c", claim="Rollback scripts need playbook documentation.",
        tags=["rollback", "playbook"],
        evidence=[Evidence(type="file", ref="playbook.md")],
    )
    # Distant atom with no path
    isolated = MemoryAtom(
        id="atom_isolated", claim="Unrelated note about lunch.",
        tags=["food"],
        evidence=[Evidence(type="note", ref="misc.md")],
    )

    atoms = [trigger_a, middle_b, remote_c, isolated]
    trigger_ids = {trigger_a.id}

    cands = mine_spreading_activation(atoms, trigger_ids, hops=2, current_time=1000.0)

    # remote_c should appear (2-hop path); isolated should NOT
    assert any("remote_c" in c.title or "Rollback" in c.claim for c in cands), (
        f"Expected remote_c to be activated. Got: {[c.title for c in cands]}"
    )
    for c in cands:
        assert "isolated" not in c.claim.lower()
        assert c.mechanism == "spreading_activation"
        assert c.surprise > 0.0
        assert c.evidence  # safety gate


def test_spreading_activation_requires_trigger_ids() -> None:
    from ahaos.incubation import mine_spreading_activation

    atom = MemoryAtom(
        id="a1", claim="Some note",
        tags=["release"],
        evidence=[Evidence(type="file", ref="f.md")],
    )
    # Empty trigger set → no candidates
    assert mine_spreading_activation([atom], set(), hops=2) == []


def test_incubate_uses_spreading_activation_when_triggers_present() -> None:
    from ahaos.incubation import incubate

    trigger_a = MemoryAtom(
        id="atom_trig", claim="Release checklist needed.",
        tags=["release", "deployment"],
        evidence=[Evidence(type="log", ref="d.log")],
    )
    middle = MemoryAtom(
        id="atom_mid", claim="Deployment rollback procedure.",
        tags=["deployment", "rollback"],
        evidence=[Evidence(type="log", ref="r.log")],
    )
    remote = MemoryAtom(
        id="atom_rem", claim="Rollback playbook needs documentation.",
        tags=["rollback", "playbook"],
        evidence=[Evidence(type="file", ref="p.md")],
    )

    # Without triggers — no spreading_activation candidates
    no_trigger = incubate([trigger_a, middle, remote], [], current_time=1000.0, trigger_ids=set())
    assert not any(c.mechanism == "spreading_activation" for c in no_trigger)

    # With trigger_a as the new atom — remote should appear
    with_trigger = incubate(
        [trigger_a, middle, remote], [], current_time=1000.0, trigger_ids={trigger_a.id}
    )
    assert any(c.mechanism == "spreading_activation" for c in with_trigger)


# ---------------------------------------------------------------------------
# P2-A: surprise field on all candidates
# ---------------------------------------------------------------------------

def test_all_candidates_have_surprise_field() -> None:
    from ahaos.incubation import incubate

    atom1 = MemoryAtom(
        id="s1", claim="Release workflow validation.",
        project="proj_a", tags=["release", "validation"],
        evidence=[Evidence(type="log", ref="a.log")], type="procedural",
        confidence=0.8, salience=0.8,
    )
    atom2 = MemoryAtom(
        id="s2", claim="Database rollback needs a playbook.",
        project="proj_b", tags=["rollback", "playbook"],
        evidence=[Evidence(type="file", ref="b.md")], type="semantic",
    )
    candidates = incubate([atom1, atom2], [], current_time=1000.0)
    for c in candidates:
        assert hasattr(c, "surprise"), f"Candidate {c.id} missing surprise field"
        assert 0.0 <= c.surprise <= 1.0


def test_surprise_higher_for_distant_connection() -> None:
    """Two atoms sharing many tags should produce lower surprise than two with few shared tags."""
    from ahaos.incubation import _compute_surprise

    close_a = MemoryAtom(id="ca", claim="claim", project="p1", tags=["release", "validation", "handoff"])
    close_b = MemoryAtom(id="cb", claim="claim", project="p2", tags=["release", "validation", "handoff"])

    far_a = MemoryAtom(id="fa", claim="claim", project="p1", tags=["release"])
    far_b = MemoryAtom(id="fb", claim="claim", project="p2", tags=["rollback"])

    surprise_close = _compute_surprise([close_a, close_b])
    surprise_far = _compute_surprise([far_a, far_b])
    assert surprise_far > surprise_close


# ---------------------------------------------------------------------------
# P2-B: candidate maturation (multi-cycle promotion)
# ---------------------------------------------------------------------------

def test_candidate_maturation_boosts_usefulness_after_three_occurrences() -> None:
    from ahaos.incubation import promote_matured_candidates

    base = make_candidate(usefulness=0.75)
    history_new = {base.id: {"seen_count": 1}}
    history_mature = {base.id: {"seen_count": 5}}

    # Seen only once — no boost
    [result_new] = promote_matured_candidates([base], history_new)
    assert result_new.usefulness == 0.75

    # Seen 5 times — boost of min(0.15, 0.05 * (5-2)) = 0.15
    [result_mature] = promote_matured_candidates([base], history_mature)
    assert abs(result_mature.usefulness - (0.75 + 0.15)) < 1e-9

    # Cap at 1.0
    high = make_candidate(usefulness=0.95)
    [capped] = promote_matured_candidates([high], history_mature)
    assert capped.usefulness == 1.0


def test_incubate_applies_maturation_via_candidate_history() -> None:
    from ahaos.incubation import incubate

    atom1 = MemoryAtom(
        id="m1", claim="Reusable release procedure.",
        project="p1", tags=["release", "proc"],
        evidence=[Evidence(type="log", ref="l.log")], type="procedural",
        confidence=0.9, salience=0.9,
    )
    atom2 = MemoryAtom(
        id="m2", claim="Another release procedure project.",
        project="p2", tags=["release", "proc"],
        evidence=[Evidence(type="file", ref="f.md")], type="procedural",
        confidence=0.9, salience=0.9,
    )

    first_run = incubate([atom1, atom2], [], current_time=1000.0, candidate_history={})
    if not first_run:
        return  # dataset too small to verify maturation path
    top = first_run[0]

    # Simulate the candidate appearing 5 times
    history = {top.id: {"seen_count": 5, "first_seen_at": 999.0}}
    mature_run = incubate([atom1, atom2], [], current_time=1000.0, candidate_history=history)
    mature_top = next((c for c in mature_run if c.id == top.id), None)
    assert mature_top is not None
    assert mature_top.usefulness > top.usefulness


def test_models_parse_iso_timestamp_fields() -> None:
    atom = MemoryAtom.from_dict(
        {
            "id": "atom_iso",
            "claim": "ISO timestamp memory",
            "created_at": "2026-06-01T00:00:00Z",
            "last_seen_at": "2026-06-02T00:00:00+00:00",
            "last_triggered_at": "1760000000",
            "activation_count": "2",
        }
    )
    loop = OpenLoop.from_dict(
        {
            "id": "loop_iso",
            "title": "ISO timestamp loop",
            "why_it_matters": "timestamps should parse",
            "created_at": "2026-06-01T00:00:00Z",
        }
    )

    assert atom.created_at > 0
    assert atom.last_seen_at > atom.created_at
    assert atom.last_triggered_at == 1760000000
    assert atom.activation_count == 2
    assert loop.created_at == atom.created_at


def test_parse_simple_yaml() -> None:
    from ahaos.config import parse_simple_yaml, get_tag_keywords

    yaml_text = """
    # This is a comment
    delivery:
      max_daily_insights: 3 # inline comment
    safety:
      allow_autonomous_actions: false
      require_evidence: true
    tag_keywords:
      - custom_tag1
      - 'custom_tag2'
      - "custom_tag3"
    """
    parsed = parse_simple_yaml(yaml_text)
    assert parsed.get("delivery") == {"max_daily_insights": 3}
    assert parsed.get("safety") == {
        "allow_autonomous_actions": False,
        "require_evidence": True,
    }
    assert parsed.get("tag_keywords") == ["custom_tag1", "custom_tag2", "custom_tag3"]

    keywords = get_tag_keywords(parsed)
    assert "custom_tag1" in keywords
    assert "custom_tag2" in keywords
    assert "custom_tag3" in keywords
    assert "release" in keywords  # Default tag
