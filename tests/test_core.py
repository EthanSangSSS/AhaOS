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
            )
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


def test_time_pressure_age_boost() -> None:
    # MemoryAtom age boost
    base_atom = MemoryAtom(
        id="mem_age_1",
        claim="Claim for age boost",
        type="semantic",
        confidence=0.5,
        salience=0.5,
        created_at=100.0,
    )
    p_young = memory_pressure(base_atom, current_time=100.0)
    p_old = memory_pressure(base_atom, current_time=40000.0)
    p_capped = memory_pressure(base_atom, current_time=60000.0)

    assert p_old > p_young
    assert p_capped == p_old

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
    pl_capped = loop_pressure(base_loop, current_time=60000.0)

    assert pl_old > pl_young
    assert pl_capped == pl_old


def test_dynamic_novelty() -> None:
    from ahaos.incubation import mine_cross_project_patterns
    atom1 = MemoryAtom(id="a1", claim="test claim", project="p1", tags=["tag1"], evidence=[Evidence(type="log", ref="1")])
    atom2 = MemoryAtom(id="a2", claim="test claim", project="p2", tags=["tag1"], evidence=[Evidence(type="log", ref="2")])
    cands_few = mine_cross_project_patterns([atom1, atom2], current_time=100.0)

    atom3 = MemoryAtom(id="a3", claim="test claim", project="p3", tags=["tag1"], evidence=[Evidence(type="log", ref="3"), Evidence(type="log", ref="4")])
    cands_many = mine_cross_project_patterns([atom1, atom2, atom3], current_time=100.0)

    assert len(cands_few) == 1
    assert len(cands_many) == 1
    assert cands_many[0].novelty > cands_few[0].novelty


def test_negative_space() -> None:
    from ahaos.incubation import mine_negative_space, incubate
    atom1 = MemoryAtom(id="a1", claim="unresolved issue for tagging", tags=["tag1"], type="semantic")
    atom2 = MemoryAtom(id="a2", claim="another issue for tagging", tags=["tag1"], type="semantic")

    cands = mine_negative_space([atom1, atom2], current_time=100.0)
    assert len(cands) == 1
    assert cands[0].mechanism == "negative_space"
    assert cands[0].title == "Missing procedural solution for `tag1`"

    atom3 = MemoryAtom(id="a3", claim="procedural rule for tagging", tags=["tag1"], type="procedural")
    cands_with_proc = mine_negative_space([atom1, atom2, atom3], current_time=100.0)
    assert len(cands_with_proc) == 0

    cands_incubated = incubate([atom1, atom2], [], current_time=100.0)
    assert any(c.mechanism == "negative_space" for c in cands_incubated)


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
