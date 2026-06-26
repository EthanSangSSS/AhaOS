from __future__ import annotations

import argparse
from pathlib import Path

from .incubation import incubate
from .report import render_markdown_report, write_report
from .storage_jsonl import load_memory_atoms, load_open_loops, validate_memory_dir
from .verification import filter_verified


def cmd_init(args: argparse.Namespace) -> int:
    base = Path(args.path)
    for rel in [
        ".ahaos/memory",
        ".ahaos/reports",
    ]:
        (base / rel).mkdir(parents=True, exist_ok=True)

    for filename in ["atoms.jsonl", "open_loops.jsonl", "insights.jsonl", "failures.jsonl"]:
        path = base / ".ahaos" / "memory" / filename
        if not path.exists():
            path.write_text("", encoding="utf-8")

    config = base / ".ahaos" / "config.yaml"
    if not config.exists():
        config.write_text(
            "delivery:\n"
            "  max_daily_insights: 3\n"
            "safety:\n"
            "  allow_autonomous_actions: false\n"
            "  require_evidence: true\n",
            encoding="utf-8",
        )

    print(f"Initialized AhaOS workspace at {base / '.ahaos'}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    errors = validate_memory_dir(Path(args.memory_dir))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Memory directory is valid.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    memory_dir = Path(args.memory_dir)
    report_dir = Path(args.report_dir)

    errors = validate_memory_dir(memory_dir)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    # Load configuration
    from .config import load_config
    config_path = memory_dir.parent / "config.yaml"
    config = load_config(config_path)

    # Respect max_daily_insights config
    top_k = args.top_k
    if top_k == 3:  # the default from argparse
        delivery = config.get("delivery", {})
        if isinstance(delivery, dict) and "max_daily_insights" in delivery:
            top_k = int(delivery["max_daily_insights"])

    # Respect safety settings from config
    safety = config.get("safety", {})
    require_evidence = True
    if isinstance(safety, dict) and "require_evidence" in safety:
        require_evidence = bool(safety["require_evidence"])

    atoms = load_memory_atoms(memory_dir)
    loops = load_open_loops(memory_dir)
    candidates = incubate(atoms, loops)
    verified = filter_verified(candidates, require_evidence=require_evidence)
    verified.sort(key=lambda c: c.score, reverse=True)
    report = render_markdown_report(verified, top_k=top_k)

    if args.dry_run:
        print(report)
        return 0

    path = write_report(report_dir, report)
    print(f"Wrote report: {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ahaos", description="AhaOS insight engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Initialize a local AhaOS workspace")
    p_init.add_argument("--path", default=".", help="Workspace root")
    p_init.set_defaults(func=cmd_init)

    p_validate = sub.add_parser("validate", help="Validate memory JSONL files")
    p_validate.add_argument("--memory-dir", default=".ahaos/memory")
    p_validate.set_defaults(func=cmd_validate)

    p_run = sub.add_parser("run", help="Generate a verified insight report")
    p_run.add_argument("--memory-dir", default=".ahaos/memory")
    p_run.add_argument("--report-dir", default=".ahaos/reports")
    p_run.add_argument("--top-k", type=int, default=3)
    p_run.add_argument("--since", default="24h", help="Reserved for future event filtering")
    p_run.add_argument("--dry-run", action="store_true")
    p_run.set_defaults(func=cmd_run)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
