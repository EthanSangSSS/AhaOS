from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .models import MemoryAtom, OpenLoop


class JsonlError(ValueError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise JsonlError(f"{path}:{idx}: invalid JSONL: {exc}") from exc
            if not isinstance(value, dict):
                raise JsonlError(f"{path}:{idx}: JSONL row must be an object")
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_memory_atoms(memory_dir: Path) -> list[MemoryAtom]:
    rows = read_jsonl(memory_dir / "atoms.jsonl")
    atoms = [MemoryAtom.from_dict(row) for row in rows]
    return [atom for atom in atoms if atom.status == "active"]


def load_open_loops(memory_dir: Path) -> list[OpenLoop]:
    rows = read_jsonl(memory_dir / "open_loops.jsonl")
    loops = [OpenLoop.from_dict(row) for row in rows]
    return [loop for loop in loops if loop.status == "open"]


def validate_memory_dir(memory_dir: Path) -> list[str]:
    errors: list[str] = []
    for filename in ["atoms.jsonl", "open_loops.jsonl"]:
        try:
            read_jsonl(memory_dir / filename)
        except Exception as exc:  # noqa: BLE001 - validation should collect all parse errors
            errors.append(str(exc))
    try:
        load_memory_atoms(memory_dir)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"atoms schema error: {exc}")
    try:
        load_open_loops(memory_dir)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"open_loops schema error: {exc}")
    return errors
