from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any, Iterable

from .atomize import infer_memory_type, infer_tags
from .storage_jsonl import read_jsonl


STAGES = {"preflight", "midflight", "final"}
VERDICTS = {"accepted", "rejected", "verified", "helped"}
_SENSITIVE_MARKERS = (
    "sk-",
    "ghp_",
    "github_pat_",
    "akia",
    "xoxb-",
    "begin private key",
    "private key",
    "client_secret",
    "refresh_token",
    "access_token",
)
_EMAIL_PATTERN = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


@dataclass(frozen=True)
class ProjectPaths:
    project_dir: Path
    input_dir: Path
    work_dir: Path
    report_dir: Path
    runs_path: Path
    feedback_path: Path


def default_state_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AhaOS"
    return Path.home() / ".local" / "share" / "ahaos"


def project_paths(state_root: Path, project: str) -> ProjectPaths:
    project_text = project.strip() or "global"
    label = Path(project_text).name or "global"
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", label).strip("-").lower() or "global"
    digest = sha1(project_text.encode("utf-8")).hexdigest()[:10]
    project_dir = Path(state_root).expanduser() / "projects" / f"{slug}-{digest}"
    return ProjectPaths(
        project_dir=project_dir,
        input_dir=project_dir / "input",
        work_dir=project_dir / "work",
        report_dir=project_dir / "reports",
        runs_path=project_dir / "runs.jsonl",
        feedback_path=project_dir / "feedback.jsonl",
    )


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _safe_summary(value: str) -> str:
    normalized = value.strip()
    lowered = normalized.lower()
    if not normalized:
        raise ValueError("checkpoint text must not be empty")
    if any(marker in lowered for marker in _SENSITIVE_MARKERS) or _EMAIL_PATTERN.search(normalized):
        raise ValueError("checkpoint input appears to contain sensitive data")
    return normalized[:500]


def _event_id(project: str, stage: str, text: str, now: float, index: int) -> str:
    payload = f"{project}:{stage}:{now:.6f}:{index}:{text}"
    return f"atom_{sha1(payload.encode('utf-8')).hexdigest()[:16]}"


def capture_checkpoint(
    *,
    state_root: Path,
    project: str,
    stage: str,
    goal: str,
    observations: Iterable[str],
    open_loops: Iterable[str] = (),
    priority: str = "P2",
) -> dict[str, Any]:
    if stage not in STAGES:
        raise ValueError(f"unsupported checkpoint stage: {stage}")
    if priority not in {"P0", "P1", "P2", "P3"}:
        raise ValueError(f"unsupported priority: {priority}")

    safe_goal = _safe_summary(goal)
    safe_observations = [_safe_summary(value) for value in observations]
    safe_loops = [_safe_summary(value) for value in open_loops]
    if not safe_observations and not safe_loops:
        raise ValueError("provide at least one observation or open loop")

    paths = project_paths(state_root, project)
    paths.input_dir.mkdir(parents=True, exist_ok=True)
    events_path = paths.input_dir / "events.jsonl"
    now = time.time()
    atom_ids: list[str] = []
    project_label = Path(project.strip() or "global").name or "global"

    for index, observation in enumerate(safe_observations):
        atom_id = _event_id(project, stage, observation, now, index)
        atom_ids.append(atom_id)
        _append_jsonl(
            events_path,
            {
                "id": atom_id,
                "claim": observation,
                "type": infer_memory_type(observation),
                "project": project_label,
                "evidence": [
                    {
                        "type": "agent_checkpoint",
                        "ref": f"{stage}:{int(now * 1000)}:{index}",
                        "quote": observation,
                        "trust_level": "user_statement",
                    }
                ],
                "confidence": 0.75,
                "salience": 0.7,
                "tags": infer_tags(f"{safe_goal} {observation}"),
                "status": "active",
                "created_at": now,
                "last_seen_at": now,
                "last_triggered_at": 0.0,
                "activation_count": 0,
                "checkpoint_stage": stage,
                "goal": safe_goal,
            },
        )

    for index, title in enumerate(safe_loops):
        loop_id = _event_id(project, stage, f"loop:{title}", now, index).replace("atom_", "loop_", 1)
        _append_jsonl(
            events_path,
            {
                "id": loop_id,
                "title": title,
                "why_it_matters": safe_goal,
                "project": project_label,
                "priority": priority,
                "status": "open",
                "related_memories": atom_ids,
                "created_at": now,
                "last_seen_at": now,
                "last_triggered_at": 0.0,
                "activation_count": 0,
                "checkpoint_stage": stage,
            },
        )

    return {"project_dir": str(paths.project_dir), "atom_ids": atom_ids, "open_loops": len(safe_loops)}


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _delivered_count(report: str) -> int:
    match = re.search(r"Delivered insights: (\d+)", report)
    return int(match.group(1)) if match else 0


def run_checkpoint(*, state_root: Path, project: str, stage: str, top_k: int = 3) -> dict[str, Any]:
    if stage not in STAGES:
        raise ValueError(f"unsupported checkpoint stage: {stage}")
    paths = project_paths(state_root, project)
    if not (paths.input_dir / "events.jsonl").exists():
        raise ValueError("no captured checkpoint events for this project")

    from scripts.pilot import run_pilot

    report_path = run_pilot(paths.input_dir, paths.work_dir, paths.report_dir, top_k=top_k, dry_run=False)
    report = Path(report_path).read_text(encoding="utf-8")
    now = time.time()
    record = {
        "run_id": f"run_{sha1(f'{project}:{stage}:{now:.6f}'.encode('utf-8')).hexdigest()[:16]}",
        "created_at": now,
        "stage": stage,
        "report_path": str(report_path),
        "candidate_count": _line_count(paths.work_dir / "aha_candidates.jsonl"),
        "latent_link_count": _line_count(paths.work_dir / "latent_links.jsonl"),
        "trigger_candidate_count": _line_count(paths.work_dir / "trigger_candidates.jsonl"),
        "delivered_count": _delivered_count(report),
    }
    _append_jsonl(paths.runs_path, record)
    return record


def record_feedback(
    *,
    state_root: Path,
    project: str,
    candidate_id: str,
    verdict: str,
    note: str,
) -> dict[str, Any]:
    if verdict not in VERDICTS:
        raise ValueError(f"unsupported feedback verdict: {verdict}")
    if not candidate_id.strip():
        raise ValueError("candidate_id must not be empty")
    paths = project_paths(state_root, project)
    row = {
        "candidate_id": candidate_id.strip(),
        "verdict": verdict,
        "note": _safe_summary(note),
        "created_at": time.time(),
    }
    _append_jsonl(paths.feedback_path, row)
    return row


def summarize_metrics(*, state_root: Path, project: str) -> dict[str, Any]:
    paths = project_paths(state_root, project)
    captured = read_jsonl(paths.input_dir / "events.jsonl")
    runs = read_jsonl(paths.runs_path)
    feedback = read_jsonl(paths.feedback_path)
    verdicts = Counter(str(row.get("verdict", "unknown")) for row in feedback)
    return {
        "project_dir": str(paths.project_dir),
        "captured_atoms": sum(1 for row in captured if "claim" in row),
        "open_loops": sum(1 for row in captured if "title" in row),
        "runs": len(runs),
        "delivered_insights": sum(int(row.get("delivered_count", 0)) for row in runs),
        "feedback": dict(sorted(verdicts.items())),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture and evaluate bounded AhaOS agent checkpoints.")
    parser.add_argument("--state-root", type=Path, default=default_state_root())
    sub = parser.add_subparsers(dest="command", required=True)

    checkpoint = sub.add_parser("checkpoint", help="Capture an explicit task summary and run the pilot.")
    checkpoint.add_argument("--project", required=True)
    checkpoint.add_argument("--stage", choices=sorted(STAGES), required=True)
    checkpoint.add_argument("--goal", required=True)
    checkpoint.add_argument("--observation", action="append", default=[])
    checkpoint.add_argument("--open-loop", action="append", default=[])
    checkpoint.add_argument("--priority", choices=["P0", "P1", "P2", "P3"], default="P2")
    checkpoint.add_argument("--top-k", type=int, default=3)

    run = sub.add_parser("run", help="Run the pilot over a project's captured events.")
    run.add_argument("--project", required=True)
    run.add_argument("--stage", choices=sorted(STAGES), required=True)
    run.add_argument("--top-k", type=int, default=3)

    feedback = sub.add_parser("feedback", help="Record whether a candidate proved useful.")
    feedback.add_argument("--project", required=True)
    feedback.add_argument("--candidate-id", required=True)
    feedback.add_argument("--verdict", choices=sorted(VERDICTS), required=True)
    feedback.add_argument("--note", required=True)

    metrics = sub.add_parser("metrics", help="Summarize checkpoint feedback and delivery counts.")
    metrics.add_argument("--project", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "checkpoint":
        captured = capture_checkpoint(
            state_root=args.state_root,
            project=args.project,
            stage=args.stage,
            goal=args.goal,
            observations=args.observation,
            open_loops=args.open_loop,
            priority=args.priority,
        )
        result = {"captured": captured, "run": run_checkpoint(state_root=args.state_root, project=args.project, stage=args.stage, top_k=args.top_k)}
    elif args.command == "run":
        result = run_checkpoint(state_root=args.state_root, project=args.project, stage=args.stage, top_k=args.top_k)
    elif args.command == "feedback":
        result = record_feedback(
            state_root=args.state_root,
            project=args.project,
            candidate_id=args.candidate_id,
            verdict=args.verdict,
            note=args.note,
        )
    else:
        result = summarize_metrics(state_root=args.state_root, project=args.project)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0
