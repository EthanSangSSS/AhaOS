#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ahaos.incubation import incubate
from ahaos.report import render_markdown_report, write_report
from ahaos.storage_jsonl import (
    load_memory_atoms,
    load_open_loops,
    validate_memory_dir,
    write_jsonl,
)
from ahaos.verification import filter_verified


ALLOWED_SUFFIXES = {".md", ".txt", ".jsonl"}
BLOCKED_NAMES = {
    ".env",
    ".git",
    ".ssh",
    ".config",
}
BLOCKED_EXTENSIONS = {
    ".env",
    ".key",
    ".pem",
}
BLOCKED_NAME_PARTS = {
    "auth",
    "browser",
    "credential",
    "password",
    "secret",
    "token",
}
TAG_KEYWORDS = {
    "agent",
    "cache",
    "cron",
    "database",
    "handoff",
    "incident",
    "local",
    "memory",
    "pilot",
    "release",
    "report",
    "review",
    "rollback",
    "test",
    "validation",
    "workflow",
}
GENERIC_ASSOCIATION_TERMS = {
    "agent",
    "ahaos",
    "example",
    "examples",
    "file",
    "files",
    "input",
    "local",
    "memory",
    "notes",
    "pilot",
    "python",
    "README",
    "report",
    "sample",
    "script",
    "scripts",
    "test",
}
SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"\b(?:\+?\d[\d\s().-]{8,}\d)\b"),
]


def _stable_id(prefix: str, text: str) -> str:
    return f"{prefix}_{sha1(text.encode('utf-8')).hexdigest()[:12]}"


def _contains_sensitive_personal_fact(text: str) -> bool:
    lowered = text.lower()
    if any(word in lowered for word in ("ssn", "passport", "medical", "diagnosis")):
        return True
    return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)


def _has_hidden_part(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts if part not in {"", "."})


def _has_blocked_name(path: Path) -> bool:
    lowered_parts = [part.lower() for part in path.parts]
    lowered_name = path.name.lower()
    if any(part in BLOCKED_NAMES for part in lowered_parts):
        return True
    if path.suffix.lower() in BLOCKED_EXTENSIONS:
        return True
    return any(part in lowered_name for part in BLOCKED_NAME_PARTS)


def is_allowed_input_file(path: Path, input_dir: Path) -> bool:
    try:
        relative = path.relative_to(input_dir)
    except ValueError:
        return False
    if path.is_symlink():
        return False
    if not path.is_file():
        return False
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return False
    if _has_hidden_part(relative) or _has_blocked_name(relative):
        return False
    return True


def iter_input_files(input_dir: Path) -> Iterable[Path]:
    home = Path.home().resolve()
    resolved_input = input_dir.resolve()
    if resolved_input == home:
        raise ValueError("refusing to scan the home directory")
    if not input_dir.is_dir():
        raise ValueError(f"input directory does not exist: {input_dir}")

    for path in sorted(input_dir.rglob("*")):
        relative = path.relative_to(input_dir)
        if _has_hidden_part(relative) or _has_blocked_name(relative):
            continue
        if is_allowed_input_file(path, input_dir):
            yield path


def clean_text_claim(line: str) -> str:
    cleaned = line.strip()
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"^[-*+]\s+", "", cleaned)
    cleaned = re.sub(r"^\d+[.)]\s+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def infer_tags(text: str) -> list[str]:
    tags = set()
    for tag in re.findall(r"#([A-Za-z0-9_-]+)", text):
        tags.add(tag.lower())
    for tag in re.findall(r"`([A-Za-z0-9_-]+)`", text):
        tags.add(tag.lower())
    words = {word.lower() for word in re.findall(r"[A-Za-z][A-Za-z0-9_-]*", text)}
    tags.update(words.intersection(TAG_KEYWORDS))
    return sorted(tags)


def atom_from_text(path: Path, input_dir: Path, line: str) -> dict[str, Any] | None:
    claim = clean_text_claim(line)
    if len(claim) < 12 or _contains_sensitive_personal_fact(claim):
        return None
    relative_ref = str(path.relative_to(input_dir))
    t = time.time()
    return {
        "id": _stable_id("atom", f"{relative_ref}:{claim}"),
        "claim": claim[:240],
        "type": "semantic",
        "project": path.stem,
        "evidence": [
            {
                "type": "local_file",
                "ref": relative_ref,
                "quote": line.strip()[:300],
                "trust_level": "first_party_file",
            }
        ],
        "confidence": 0.7,
        "salience": 0.65,
        "tags": infer_tags(claim),
        "status": "active",
        "created_at": t,
        "last_seen_at": t,
        "last_triggered_at": 0.0,
        "activation_count": 0,
    }


def existing_atom(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row.get("claim"), str):
        return None
    claim = row["claim"].strip()
    if not claim or _contains_sensitive_personal_fact(claim):
        return None
    atom = dict(row)
    atom.setdefault("id", _stable_id("atom", claim))
    atom.setdefault("type", "semantic")
    atom.setdefault("project", "local_jsonl")
    atom.setdefault("evidence", [])
    atom.setdefault("confidence", 0.5)
    atom.setdefault("salience", 0.5)
    atom.setdefault("tags", [])
    atom.setdefault("status", "active")
    atom.setdefault("created_at", 0.0)
    atom.setdefault("last_seen_at", 0.0)
    atom.setdefault("last_triggered_at", 0.0)
    atom.setdefault("activation_count", 0)
    return atom


def existing_open_loop(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row.get("title"), str):
        return None
    loop = dict(row)
    loop.setdefault("id", _stable_id("loop", loop["title"]))
    loop.setdefault("why_it_matters", "")
    loop.setdefault("project", "local_jsonl")
    loop.setdefault("priority", "P2")
    loop.setdefault("status", "open")
    loop.setdefault("related_memories", [])
    loop.setdefault("created_at", 0.0)
    loop.setdefault("last_seen_at", 0.0)
    loop.setdefault("last_triggered_at", 0.0)
    loop.setdefault("activation_count", 0)
    return loop


def load_local_inputs(input_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    atoms: list[dict[str, Any]] = []
    loops: list[dict[str, Any]] = []
    for path in iter_input_files(input_dir):
        if path.suffix.lower() == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    continue
                atom = existing_atom(row)
                if atom is not None:
                    atoms.append(atom)
                    continue
                loop = existing_open_loop(row)
                if loop is not None:
                    loops.append(loop)
            continue

        for line in path.read_text(encoding="utf-8").splitlines():
            atom = atom_from_text(path, input_dir, line)
            if atom is not None:
                atoms.append(atom)
    return atoms, loops


def write_temp_memory(work_dir: Path, atoms: list[dict[str, Any]], loops: list[dict[str, Any]]) -> None:
    write_jsonl(work_dir / "atoms.jsonl", atoms)
    write_jsonl(work_dir / "open_loops.jsonl", loops)


def load_pilot_state(work_dir: Path) -> dict[str, Any]:
    state_path = work_dir / "state.json"
    if not state_path.exists():
        return {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return state if isinstance(state, dict) else {}


def numeric_timestamp(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return default
    return default


def apply_seen_metadata(
    rows: list[dict[str, Any]],
    meta_by_id: dict[str, Any],
    now: float,
) -> None:
    for row in rows:
        row_id = str(row.get("id", ""))
        previous = meta_by_id.get(row_id, {})
        if not isinstance(previous, dict):
            previous = {}
        previous_created = numeric_timestamp(previous.get("created_at"))
        explicit_created = numeric_timestamp(row.get("created_at"))
        row["created_at"] = previous_created or explicit_created or now
        row["last_seen_at"] = now
        row.setdefault("last_triggered_at", numeric_timestamp(previous.get("last_triggered_at")))
        row.setdefault("activation_count", int(previous.get("activation_count", 0) or 0))


def mark_trigger_metadata(rows: list[dict[str, Any]], trigger_ids: set[str], now: float) -> None:
    for row in rows:
        if row.get("id") not in trigger_ids:
            continue
        row["last_triggered_at"] = now
        row["activation_count"] = int(row.get("activation_count", 0) or 0) + 1


def mark_activated_metadata(
    rows: list[dict[str, Any]],
    activated_ids: set[str],
    initial_trigger_ids: set[str],
    now: float,
) -> None:
    for row in rows:
        row_id = str(row.get("id", ""))
        if row_id not in activated_ids or row_id in initial_trigger_ids:
            continue
        row["last_triggered_at"] = now
        row["activation_count"] = int(row.get("activation_count", 0) or 0) + 1


def save_pilot_state(
    work_dir: Path,
    atoms: list[dict[str, Any]],
    loops: list[dict[str, Any]],
    now: float,
) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "last_run_at": now,
        "last_atom_ids": sorted(str(atom["id"]) for atom in atoms),
        "last_loop_ids": sorted(str(loop["id"]) for loop in loops),
        "atom_meta": {
            str(atom["id"]): {
                "created_at": atom.get("created_at", 0.0),
                "last_seen_at": atom.get("last_seen_at", 0.0),
                "last_triggered_at": atom.get("last_triggered_at", 0.0),
                "activation_count": atom.get("activation_count", 0),
            }
            for atom in atoms
        },
        "loop_meta": {
            str(loop["id"]): {
                "created_at": loop.get("created_at", 0.0),
                "last_seen_at": loop.get("last_seen_at", 0.0),
                "last_triggered_at": loop.get("last_triggered_at", 0.0),
                "activation_count": loop.get("activation_count", 0),
            }
            for loop in loops
        },
    }
    (work_dir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def get_sig_words(claim: str) -> set[str]:
    words = set(re.findall(r"\b[a-zA-Z]{4,}\b", claim.lower()))
    stop_words = {
        "about",
        "could",
        "from",
        "have",
        "ahaos",
        "input",
        "local",
        "memory",
        "need",
        "needs",
        "notes",
        "other",
        "pilot",
        "python",
        "sample",
        "script",
        "scripts",
        "should",
        "that",
        "their",
        "there",
        "this",
        "with",
        "would",
    }
    return words - stop_words


def extract_structural_signature(claim: str) -> dict[str, str | None]:
    lowered = claim.lower()
    slots = {}

    # problem slot
    prob_match = re.search(r"\b(need[s]?|fail(?:ure)?|issue|error|bug|incident|problem|missing|unresolved)\b\s*(\w+(?:\s+\w+){0,3})", lowered)
    slots["problem"] = prob_match.group(0) if prob_match else None

    # constraint slot
    const_match = re.search(r"\b(must|should|cannot|rule|limit|restrict|block|prevent|require[s]?)\b\s*(\w+(?:\s+\w+){0,3})", lowered)
    slots["constraint"] = const_match.group(0) if const_match else None

    # action slot
    act_match = re.search(r"\b(run|execute|verify|check|validate|implement|convert|checklist|define|update|test|create)\b\s*(\w+(?:\s+\w+){0,3})", lowered)
    slots["action"] = act_match.group(0) if act_match else None

    # evidence slot
    ev_match = re.search(r"\b(log|report|telemetry|file|source|quote|history|found|observe[d]?)\b\s*(\w+(?:\s+\w+){0,3})", lowered)
    slots["evidence"] = ev_match.group(0) if ev_match else None

    # open loop slot
    ol_match = re.search(r"\b(loop|reminder|follow-up|open|pending|track)\b\s*(\w+(?:\s+\w+){0,3})", lowered)
    slots["open_loop"] = ol_match.group(0) if ol_match else None

    return slots


def generate_candidates_and_links(
    atoms: list[Any], loops: list[Any], trigger_atom_ids: set[str] | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if trigger_atom_ids is None:
        trigger_atom_ids = set()

    candidates: dict[str, dict[str, Any]] = {}
    links: dict[str, dict[str, Any]] = {}

    def annotate_trigger_and_boost(
        item: dict[str, Any], source_ids: list[str], score_key: str = "score"
    ) -> None:
        triggered_by = [aid for aid in source_ids if aid in trigger_atom_ids]
        if triggered_by:
            item["triggered_by_atom_ids"] = triggered_by
            is_new_activating_old = any(aid in trigger_atom_ids for aid in source_ids) and any(aid not in trigger_atom_ids for aid in source_ids)
            if is_new_activating_old:
                item[score_key] = round(min(1.0, item[score_key] + 0.05), 2)

    # 1. repeated_tag heuristic
    tag_to_atoms = defaultdict(list)
    for atom in atoms:
        for tag in atom.tags:
            if tag in GENERIC_ASSOCIATION_TERMS:
                continue
            tag_to_atoms[tag].append(atom)

    for tag, group in tag_to_atoms.items():
        if len(group) >= 2:
            source_ids = sorted(list({atom.id for atom in group}))
            evidence_refs = sorted({ev.ref for atom in group for ev in atom.evidence if ev.ref})

            link_id = _stable_id("link", f"repeated_tag:{tag}:" + ",".join(source_ids))
            links[link_id] = {
                "id": link_id,
                "reason": f"Multiple memory atoms ({len(group)}) share tag '{tag}'",
                "association_type": "repeated_tag",
                "source_atom_ids": source_ids,
                "score": round(min(0.95, 0.5 + 0.1 * len(source_ids)), 2),
                "status": "latent",
            }
            annotate_trigger_and_boost(links[link_id], source_ids, "score")

            cand_id = _stable_id("cand", f"repeated_tag:{tag}:" + ",".join(source_ids))
            candidates[cand_id] = {
                "id": cand_id,
                "title": f"Repeated tag pattern: {tag}",
                "hypothesis": (
                    f"The tag '{tag}' appears in multiple context areas, which may point to a "
                    "recurring design or practice."
                ),
                "association_type": "repeated_tag",
                "source_atom_ids": source_ids,
                "evidence_refs": evidence_refs,
                "aha_score": round(min(0.95, 0.6 + 0.1 * len(source_ids)), 2),
                "status": "candidate",
                "boundary": "Ensure tag usage represents actual conceptual overlap before applying shared patterns.",
                "next_smallest_check": f"Examine the occurrences of tag '{tag}' to map common properties.",
            }
            annotate_trigger_and_boost(candidates[cand_id], source_ids, "aha_score")

    # 2. structural_echo heuristic
    for i in range(len(atoms)):
        for j in range(i + 1, len(atoms)):
            a, b = atoms[i], atoms[j]
            words_a = get_sig_words(a.claim)
            words_b = get_sig_words(b.claim)
            common = words_a.intersection(words_b)

            sig_a = extract_structural_signature(a.claim)
            sig_b = extract_structural_signature(b.claim)
            shared_slots = {
                k: [sig_a[k], sig_b[k]]
                for k in sig_a
                if sig_a[k] is not None and sig_b[k] is not None
            }

            if len(common) >= 2 or len(shared_slots) >= 2:
                source_ids = sorted([a.id, b.id])
                evidence_refs = sorted({ev.ref for atom in (a, b) for ev in atom.evidence if ev.ref})

                # word jaccard distance
                union_words = words_a.union(words_b)
                word_dist = 1.0 - len(common) / len(union_words) if union_words else 1.0

                # slot jaccard distance
                slots_a = {k for k, v in sig_a.items() if v is not None}
                slots_b = {k for k, v in sig_b.items() if v is not None}
                union_slots = slots_a.union(slots_b)
                slot_dist = 1.0 - len(slots_a.intersection(slots_b)) / len(union_slots) if union_slots else 1.0

                structural_distance = round(0.5 * word_dist + 0.5 * slot_dist, 3)
                shared_structure = shared_slots

                score = round(min(0.9, 0.4 + 0.1 * len(common) + 0.1 * len(shared_slots)), 2)
                aha_score = round(min(0.9, 0.5 + 0.1 * len(common) + 0.1 * len(shared_slots)), 2)

                link_id = _stable_id("link", "structural_echo:" + ",".join(source_ids))
                links[link_id] = {
                    "id": link_id,
                    "reason": (
                        "Atoms exhibit structural echo with shared vocabulary: "
                        f"{sorted(common)} and shared slots: {list(shared_structure.keys())}"
                    ),
                    "association_type": "structural_echo",
                    "source_atom_ids": source_ids,
                    "score": score,
                    "status": "latent",
                    "shared_structure": shared_structure,
                    "structural_distance": structural_distance,
                }
                annotate_trigger_and_boost(links[link_id], source_ids, "score")

                cand_id = _stable_id("cand", "structural_echo:" + ",".join(source_ids))
                candidates[cand_id] = {
                    "id": cand_id,
                    "title": f"Structural similarity around: {', '.join(sorted(common)[:2]) if common else list(shared_structure.keys())[0]}",
                    "hypothesis": (
                        f"The claims share key vocabulary {sorted(common)} and structure {list(shared_structure.keys())}, suggesting a "
                        "possible shared underlying rule."
                    ),
                    "association_type": "structural_echo",
                    "source_atom_ids": source_ids,
                    "evidence_refs": evidence_refs,
                    "aha_score": aha_score,
                    "status": "candidate",
                    "boundary": "Ensure semantic meaning is aligned before consolidating.",
                    "next_smallest_check": "Check if these memory atoms represent the same underlying requirement or rule.",
                    "shared_structure": shared_structure,
                    "structural_distance": structural_distance,
                }
                annotate_trigger_and_boost(candidates[cand_id], source_ids, "aha_score")

    # 3. open_loop_bridge heuristic
    for loop in loops:
        loop_tags = set(infer_tags(loop.title) + infer_tags(loop.why_it_matters))
        loop_words = get_sig_words(loop.title + " " + loop.why_it_matters)

        for atom in atoms:
            is_explicit = atom.id in loop.related_memories
            shared_tags = set(atom.tags).intersection(loop_tags) - GENERIC_ASSOCIATION_TERMS
            shared_words = get_sig_words(atom.claim).intersection(loop_words)

            if is_explicit or shared_tags or len(shared_words) >= 2:
                source_atom_ids = [atom.id]
                evidence_refs = sorted({ev.ref for ev in atom.evidence if ev.ref})

                reason_parts = []
                if is_explicit:
                    reason_parts.append("explicitly linked")
                if shared_tags:
                    reason_parts.append(f"shared tags {sorted(shared_tags)}")
                if len(shared_words) >= 2:
                    reason_parts.append(f"shared vocabulary {sorted(shared_words)}")
                reason_str = "Open loop bridges to memory atom via " + " and ".join(reason_parts)

                link_id = _stable_id("link", f"open_loop_bridge:{loop.id}:{atom.id}")
                links[link_id] = {
                    "id": link_id,
                    "reason": reason_str,
                    "association_type": "open_loop_bridge",
                    "source_atom_ids": source_atom_ids,
                    "source_loop_ids": [loop.id],
                    "score": 0.8 if is_explicit else 0.7,
                    "status": "latent",
                }
                annotate_trigger_and_boost(links[link_id], source_atom_ids, "score")

                cand_id = _stable_id("cand", f"open_loop_bridge:{loop.id}:{atom.id}")
                candidates[cand_id] = {
                    "id": cand_id,
                    "title": f"Open loop bridge: {loop.title[:40]}...",
                    "hypothesis": (
                        f"The active open loop '{loop.title}' may be informed by the memory "
                        f"atom '{atom.claim}'."
                    ),
                    "association_type": "open_loop_bridge",
                    "source_atom_ids": source_atom_ids,
                    "source_loop_ids": [loop.id],
                    "evidence_refs": evidence_refs,
                    "aha_score": 0.8,
                    "status": "candidate",
                    "boundary": "Do not mark the open loop as resolved until validation steps succeed.",
                    "next_smallest_check": (
                        f"Verify whether the referenced claim helps bound the loop '{loop.title}'."
                    ),
                }
                annotate_trigger_and_boost(candidates[cand_id], source_atom_ids, "aha_score")

    # If trigger_atom_ids is set and not empty, prioritize triggered ones first
    def sort_key(x: dict[str, Any]) -> tuple[int, str]:
        has_triggered = 0 if x.get("triggered_by_atom_ids") else 1
        return (has_triggered, x["id"])

    return (
        sorted(candidates.values(), key=sort_key),
        sorted(links.values(), key=sort_key),
    )


def run_local_pilot(
    input_dir: Path,
    work_dir: Path,
    report_dir: Path,
    top_k: int,
    dry_run: bool,
) -> str | Path:
    now = time.time()
    state_data = load_pilot_state(work_dir)
    last_atom_ids = set(state_data.get("last_atom_ids", []))
    has_prior_state = bool(last_atom_ids)

    atoms, loops = load_local_inputs(input_dir)
    apply_seen_metadata(atoms, state_data.get("atom_meta", {}), now)
    apply_seen_metadata(loops, state_data.get("loop_meta", {}), now)

    current_atom_ids = {str(atom["id"]) for atom in atoms}
    trigger_atom_ids = current_atom_ids - last_atom_ids if has_prior_state else set()
    mark_trigger_metadata(atoms, trigger_atom_ids, now)

    write_temp_memory(work_dir, atoms, loops)

    errors = validate_memory_dir(work_dir)
    if errors:
        joined = "\n".join(errors)
        raise ValueError(f"generated memory failed validation:\n{joined}")

    loaded_atoms = load_memory_atoms(work_dir)
    loaded_loops = load_open_loops(work_dir)

    cands, lnks = generate_candidates_and_links(loaded_atoms, loaded_loops, trigger_atom_ids)
    write_jsonl(work_dir / "aha_candidates.jsonl", cands)
    write_jsonl(work_dir / "latent_links.jsonl", lnks)

    # 3. Write trigger_candidates.jsonl
    trigger_cands = [cand for cand in cands if cand.get("triggered_by_atom_ids")]
    write_jsonl(work_dir / "trigger_candidates.jsonl", trigger_cands)
    activated_atom_ids = {
        atom_id
        for candidate in trigger_cands
        for atom_id in candidate.get("source_atom_ids", [])
    }
    if activated_atom_ids:
        mark_activated_metadata(atoms, activated_atom_ids, trigger_atom_ids, now)
        write_temp_memory(work_dir, atoms, loops)

    candidates = incubate(loaded_atoms, loaded_loops)
    verified = filter_verified(candidates)
    report = render_markdown_report(verified, top_k=top_k)

    save_pilot_state(work_dir, atoms, loops, now)

    if dry_run:
        return report
    return write_report(report_dir, report)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run AhaOS against explicit local files.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--work-dir", default=Path("/tmp/ahaos-local-pilot"), type=Path)
    parser.add_argument("--report-dir", default=Path("/tmp/ahaos-local-pilot-reports"), type=Path)
    parser.add_argument("--top-k", default=3, type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_local_pilot(
            input_dir=args.input_dir,
            work_dir=args.work_dir,
            report_dir=args.report_dir,
            top_k=args.top_k,
            dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001 - CLI should return a concise failure
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(result)
    else:
        print(f"Wrote report: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
