from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.pilot import (
    apply_seen_metadata,
    atom_from_text,
    infer_tags,
    is_allowed_input_file,
    iter_input_files,
    load_local_inputs,
    mark_activated_metadata,
    main,
    run_pilot,
)


def test_input_file_safety_blocks_hidden_and_sensitive_names(tmp_path: Path) -> None:
    safe = tmp_path / "notes.md"
    safe.write_text("safe", encoding="utf-8")
    assert is_allowed_input_file(safe, tmp_path)

    hidden = tmp_path / ".hidden.md"
    hidden.write_text("hidden", encoding="utf-8")
    assert not is_allowed_input_file(hidden, tmp_path)

    secret = tmp_path / "api_token.txt"
    secret.write_text("secret", encoding="utf-8")
    assert not is_allowed_input_file(secret, tmp_path)

    unsupported = tmp_path / "notes.yaml"
    unsupported.write_text("x", encoding="utf-8")
    assert not is_allowed_input_file(unsupported, tmp_path)

    outside = tmp_path.parent / "outside_notes.md"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "linked_notes.md"
    link.symlink_to(outside)
    assert not is_allowed_input_file(link, tmp_path)


def test_iter_input_files_skips_hidden_directories(tmp_path: Path) -> None:
    visible = tmp_path / "visible"
    visible.mkdir()
    (visible / "notes.md").write_text("Release validation note.", encoding="utf-8")

    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "notes.md").write_text("Should not be read.", encoding="utf-8")

    assert list(iter_input_files(tmp_path)) == [visible / "notes.md"]


def test_iter_input_files_refuses_home() -> None:
    with pytest.raises(ValueError, match="home directory"):
        list(iter_input_files(Path.home()))


def test_load_local_inputs_generates_conservative_atoms(tmp_path: Path) -> None:
    (tmp_path / "notes.md").write_text(
        "- The `release` workflow needs local validation before handoff.\n"
        "Contact owner@example.com about a private detail.\n",
        encoding="utf-8",
    )
    (tmp_path / "events.jsonl").write_text(
        json.dumps(
            {
                "id": "atom_existing",
                "claim": "Another project has the same release validation concern.",
                "type": "procedural",
                "project": "sample_service",
                "evidence": [
                    {
                        "type": "local_file",
                        "ref": "events.jsonl",
                        "quote": "release validation concern",
                        "trust_level": "first_party_file",
                    }
                ],
                "confidence": 0.8,
                "salience": 0.8,
                "tags": ["release", "validation"],
                "status": "active",
            }
        )
        + "\n"
        + json.dumps(
            {
                "id": "loop_existing",
                "title": "Release checklist remains open",
                "why_it_matters": "The checklist blocks handoff.",
                "priority": "P1",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    atoms, loops = load_local_inputs(tmp_path)

    generated = [atom for atom in atoms if atom["id"] != "atom_existing"]
    assert len(generated) == 1
    assert generated[0]["confidence"] == 0.7
    assert generated[0]["evidence"][0]["type"] == "local_file"
    assert generated[0]["evidence"][0]["trust_level"] == "first_party_file"
    assert "release" in generated[0]["tags"]
    assert "validation" in generated[0]["tags"]
    assert any(atom["id"] == "atom_existing" for atom in atoms)
    assert loops[0]["id"] == "loop_existing"


def test_chinese_input_receives_normalized_tags_and_procedural_type(tmp_path: Path) -> None:
    tags = infer_tags("发布前必须完成验证和回滚流程 #发布")
    assert {"release", "validation", "rollback", "procedure"}.issubset(tags)

    atom = atom_from_text(
        tmp_path / "notes.md",
        tmp_path,
        "发布前必须执行验证流程，失败时按回滚清单处理。",
    )
    assert atom is not None
    assert atom["type"] == "procedural"


def test_seen_metadata_only_changes_when_an_atom_is_reactivated() -> None:
    rows = [{"id": "atom_old", "claim": "Old memory", "created_at": 10.0, "last_seen_at": 10.0}]
    prior = {"atom_old": {"created_at": 10.0, "last_seen_at": 10.0}}

    apply_seen_metadata(rows, prior, now=20.0)
    assert rows[0]["last_seen_at"] == 10.0

    mark_activated_metadata(rows, {"atom_old"}, set(), now=20.0)
    assert rows[0]["last_seen_at"] == 20.0


def test_run_pilot_writes_memory_and_report(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    work_dir = tmp_path / "work"
    report_dir = tmp_path / "reports"
    input_dir.mkdir()
    (input_dir / "notes.md").write_text(
        "- The release workflow needs a local validation checklist before handoff.\n",
        encoding="utf-8",
    )
    (input_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "id": "atom_other",
                "claim": "A different project also needs a release validation checklist.",
                "type": "procedural",
                "project": "other_project",
                "evidence": [
                    {
                        "type": "local_file",
                        "ref": "events.jsonl",
                        "quote": "release validation checklist",
                        "trust_level": "first_party_file",
                    }
                ],
                "confidence": 0.8,
                "salience": 0.8,
                "tags": ["release", "validation"],
                "status": "active",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_pilot(input_dir, work_dir, report_dir, top_k=3, dry_run=False)

    assert isinstance(result, Path)
    assert result.exists()
    assert (work_dir / "atoms.jsonl").exists()
    assert (work_dir / "open_loops.jsonl").exists()
    assert (work_dir / "aha_candidates.jsonl").exists()
    assert (work_dir / "latent_links.jsonl").exists()
    report = result.read_text(encoding="utf-8")
    assert "AhaOS Insight Report" in report
    assert "release" in report


def test_main_dry_run_prints_report_without_report_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    input_dir = tmp_path / "input"
    work_dir = tmp_path / "work"
    report_dir = tmp_path / "reports"
    input_dir.mkdir()
    (input_dir / "notes.md").write_text(
        "- The release workflow needs local validation before handoff.\n",
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--input-dir",
            str(input_dir),
            "--work-dir",
            str(work_dir),
            "--report-dir",
            str(report_dir),
            "--dry-run",
        ]
    )

    assert exit_code == 0
    assert (work_dir / "atoms.jsonl").exists()
    assert not report_dir.exists()
    assert "AhaOS Insight Report" in capsys.readouterr().out


def test_candidates_and_latent_links_generation(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    work_dir = tmp_path / "work"
    report_dir = tmp_path / "reports"
    input_dir.mkdir()

    # Note 1: triggers repeated_tag and structural_echo
    (input_dir / "notes.md").write_text(
        "- The release workflow needs local validation checklist before handoff.\n"
        "- Cron incident notes should become a bounded follow-up instead of an open-ended reminder.\n",
        encoding="utf-8",
    )
    
    # Event 1: triggers repeated_tag and structural_echo
    # Event 2: open loop (triggers open_loop_bridge)
    (input_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "id": "atom_sample_release",
                "claim": "A second project also needs a release validation checklist before handoff.",
                "type": "procedural",
                "project": "sample_service",
                "evidence": [
                    {
                        "type": "local_file",
                        "ref": "events.jsonl",
                        "quote": "release validation checklist",
                        "trust_level": "first_party_file",
                    }
                ],
                "confidence": 0.8,
                "salience": 0.8,
                "tags": ["release", "validation"],
                "status": "active",
            }
        )
        + "\n"
        + json.dumps(
            {
                "id": "loop_sample_cron",
                "title": "Cron incident notes need a bounded follow-up",
                "why_it_matters": "Incident follow-up pressure needs check.",
                "project": "sample_ops",
                "priority": "P1",
                "status": "open",
                "related_memories": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert isinstance(run_pilot(input_dir, work_dir, report_dir, top_k=3, dry_run=True), str)

    assert (work_dir / "aha_candidates.jsonl").exists()
    assert (work_dir / "latent_links.jsonl").exists()

    # Read and parse candidates
    candidates_lines = (work_dir / "aha_candidates.jsonl").read_text(encoding="utf-8").splitlines()
    candidates = [json.loads(line) for line in candidates_lines if line.strip()]

    # Read and parse links
    links_lines = (work_dir / "latent_links.jsonl").read_text(encoding="utf-8").splitlines()
    links = [json.loads(line) for line in links_lines if line.strip()]

    # Assert candidate fields
    cand_required_fields = {
        "id", "title", "hypothesis", "association_type", "source_atom_ids",
        "evidence_refs", "aha_score", "status", "boundary", "next_smallest_check"
    }
    assert len(candidates) > 0
    for cand in candidates:
        for field in cand_required_fields:
            assert field in cand, f"candidate missing field {field}"

    # Assert link fields
    link_required_fields = {
        "id", "reason", "association_type", "source_atom_ids", "score", "status"
    }
    assert len(links) > 0
    for link in links:
        for field in link_required_fields:
            assert field in link, f"link missing field {field}"

    # Check that repeated_tag, structural_echo, and open_loop_bridge are found
    assoc_types_found = {cand["association_type"] for cand in candidates}
    assert "repeated_tag" in assoc_types_found
    assert "structural_echo" in assoc_types_found
    assert "open_loop_bridge" in assoc_types_found
    assert all(cand["title"] != "Repeated tag pattern: local" for cand in candidates)
    open_loop_candidates = [
        cand for cand in candidates if cand["association_type"] == "open_loop_bridge"
    ]
    assert open_loop_candidates
    assert all("source_loop_ids" in cand for cand in open_loop_candidates)
    assert all(
        all(atom_id.startswith("atom_") for atom_id in cand["source_atom_ids"])
        for cand in open_loop_candidates
    )

    link_assoc_types_found = {link["association_type"] for link in links}
    assert "repeated_tag" in link_assoc_types_found
    assert "structural_echo" in link_assoc_types_found
    assert "open_loop_bridge" in link_assoc_types_found
    open_loop_links = [link for link in links if link["association_type"] == "open_loop_bridge"]
    assert open_loop_links
    assert all("source_loop_ids" in link for link in open_loop_links)


def test_pilot_state_and_trigger_and_structural_fields(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    work_dir = tmp_path / "work"
    report_dir = tmp_path / "reports"
    input_dir.mkdir()

    # First run: create one atom
    (input_dir / "notes1.md").write_text("- The release workflow needs local validation before handoff.\n", encoding="utf-8")

    # Run first pilot execution
    run_pilot(input_dir, work_dir, report_dir, top_k=3, dry_run=True)

    # Verify state.json was created and contains the first atom ID
    state_file = work_dir / "state.json"
    assert state_file.exists()
    state_data = json.loads(state_file.read_text(encoding="utf-8"))
    last_ids = state_data.get("last_atom_ids", [])
    assert len(last_ids) == 1
    first_atom_id = last_ids[0]
    first_created_at = state_data["atom_meta"][first_atom_id]["created_at"]
    assert first_created_at > 0
    assert (work_dir / "trigger_candidates.jsonl").read_text(encoding="utf-8") == ""

    # Second run: add a second atom (which will trigger a structural echo with the first one)
    (input_dir / "notes2.md").write_text("- A second project also needs a release validation checklist before handoff.\n", encoding="utf-8")

    run_pilot(input_dir, work_dir, report_dir, top_k=3, dry_run=True)

    # Verify state.json was updated with both atoms
    state_data_updated = json.loads(state_file.read_text(encoding="utf-8"))
    last_ids_updated = state_data_updated.get("last_atom_ids", [])
    assert len(last_ids_updated) == 2
    assert first_atom_id in last_ids_updated
    assert state_data_updated["atom_meta"][first_atom_id]["created_at"] == first_created_at
    assert state_data_updated["atom_meta"][first_atom_id]["last_seen_at"] > first_created_at
    assert state_data_updated["atom_meta"][first_atom_id]["last_triggered_at"] > 0
    assert state_data_updated["atom_meta"][first_atom_id]["activation_count"] >= 1

    # Verify trigger_candidates.jsonl and triggered_by_atom_ids
    trigger_cands_file = work_dir / "trigger_candidates.jsonl"
    assert trigger_cands_file.exists()
    trigger_cands = [json.loads(line) for line in trigger_cands_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(trigger_cands) > 0

    # Each triggered candidate should have triggered_by_atom_ids
    for cand in trigger_cands:
        assert "triggered_by_atom_ids" in cand
        # Since we added notes2.md in the second run, the triggered_by_atom_ids should contain the second atom's ID
        assert any(aid != first_atom_id for aid in cand["triggered_by_atom_ids"])

    # Verify structural echo fields: shared_structure and structural_distance
    candidates_lines = (work_dir / "aha_candidates.jsonl").read_text(encoding="utf-8").splitlines()
    candidates = [json.loads(line) for line in candidates_lines if line.strip()]
    echo_cands = [c for c in candidates if c["association_type"] == "structural_echo"]
    assert len(echo_cands) > 0
    for cand in echo_cands:
        assert "shared_structure" in cand
        assert "structural_distance" in cand
        assert isinstance(cand["structural_distance"], float)
        assert "problem" in cand["shared_structure"] or "action" in cand["shared_structure"]


def test_pilot_candidate_promotion(tmp_path: Path) -> None:
    input_dir = tmp_path / "inputs"
    work_dir = tmp_path / "work"
    report_dir = tmp_path / "reports"
    input_dir.mkdir()
    report_dir.mkdir()

    # Create two claims that trigger structural_echo and have evidence
    (input_dir / "service_a.md").write_text("- The database migration must run rollback procedure on failure. [PR#1](file:///ref)\n", encoding="utf-8")
    (input_dir / "service_b.md").write_text("- The user service must run rollback procedure on failure. [PR#2](file:///ref2)\n", encoding="utf-8")

    # Run 1
    run_pilot(input_dir, work_dir, report_dir, top_k=3, dry_run=True)
    state_file = work_dir / "state.json"
    state_data1 = json.loads(state_file.read_text(encoding="utf-8"))
    cand_history1 = state_data1.get("candidate_history", {})
    assert len(cand_history1) > 0
    cand_id = list(cand_history1.keys())[0]
    assert cand_history1[cand_id]["seen_count"] == 1

    # Run 2
    run_pilot(input_dir, work_dir, report_dir, top_k=3, dry_run=True)
    state_data2 = json.loads(state_file.read_text(encoding="utf-8"))
    assert state_data2["candidate_history"][cand_id]["seen_count"] == 2

    # Run 3 (dry_run=False to generate report)
    report_path = run_pilot(input_dir, work_dir, report_dir, top_k=3, dry_run=False)
    assert isinstance(report_path, Path)
    assert report_path.exists()
    report_content = report_path.read_text(encoding="utf-8")
    
    # The structural echo candidate should now be promoted and included in the report!
    assert "Structural similarity" in report_content or "database migration" in report_content or "user service" in report_content


def test_pilot_skips_secret_tokens(tmp_path: Path) -> None:
    from scripts.pilot import load_local_inputs
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()

    # Text file contains normal lines and a secret-like line
    (input_dir / "notes.md").write_text(
        "- This is a normal memory claim that has evidence. [Doc](file:///ref)\n"
        "- This contains api_token = 'ghp_secrettoken12345' which should be skipped.\n"
        "- This is another valid memory claim with evidence. [PR](file:///ref2)\n",
        encoding="utf-8"
    )

    # jsonl contains normal line and secret-like line
    (input_dir / "events.jsonl").write_text(
        '{"id": "atom_ok", "claim": "Normal JSONL memory atom claim here.", "type": "semantic", "evidence": [{"type": "local_file", "ref": "events.jsonl", "trust_level": "first_party_file"}], "tags": ["jsonl"]}\n'
        '{"id": "atom_bad", "claim": "sk-1234567890", "type": "semantic"}\n',
        encoding="utf-8"
    )

    atoms, loops = load_local_inputs(input_dir)
    claims = {atom["claim"] for atom in atoms}
    assert "This is a normal memory claim that has evidence. [Doc](file:///ref)" in claims
    assert "This is another valid memory claim with evidence. [PR](file:///ref2)" in claims
    assert "Normal JSONL memory atom claim here." in claims

    # Secret lines must be skipped entirely
    assert not any("ghp_" in c for c in claims)
    assert not any("sk-" in c for c in claims)
