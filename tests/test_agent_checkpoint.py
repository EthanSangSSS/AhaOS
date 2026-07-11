from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ahaos.agent_memory import (
    capture_checkpoint,
    project_paths,
    record_feedback,
    run_checkpoint,
    summarize_metrics,
)


def test_checkpoint_persists_project_events_runs_and_feedback(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    project = "/work/demo-service"

    captured = capture_checkpoint(
        state_root=state_root,
        project=project,
        stage="preflight",
        goal="发布前检查迁移风险",
        observations=["数据库迁移失败后必须执行回滚验证流程。"],
        open_loops=["确认回滚步骤已被验证"],
        priority="P1",
    )
    paths = project_paths(state_root, project)
    rows = [json.loads(line) for line in paths.input_dir.joinpath("events.jsonl").read_text(encoding="utf-8").splitlines()]

    assert captured["atom_ids"]
    assert rows[0]["type"] in {"failure", "procedural"}
    assert "release" in rows[0]["tags"]
    assert paths.project_dir != project_paths(state_root, "/work/other-service").project_dir

    run = run_checkpoint(state_root=state_root, project=project, stage="preflight", top_k=3)
    assert run["run_id"]
    assert paths.runs_path.exists()

    record_feedback(
        state_root=state_root,
        project=project,
        candidate_id="cand_demo",
        verdict="helped",
        note="提醒了需要验证的回滚流程。",
    )
    summary = summarize_metrics(state_root=state_root, project=project)

    assert summary["captured_atoms"] == 1
    assert summary["runs"] == 1
    assert summary["feedback"]["helped"] == 1
