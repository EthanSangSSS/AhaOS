from __future__ import annotations

from pathlib import Path

import pytest

from ahaos.storage_jsonl import read_jsonl, write_jsonl


def test_failed_rewrite_preserves_previous_snapshot_and_cleans_temp_file(
    tmp_path: Path,
) -> None:
    target = tmp_path / "memory" / "atoms.jsonl"
    write_jsonl(target, [{"id": "old-1", "claim": "trusted prior snapshot"}])
    previous = target.read_bytes()

    with pytest.raises(TypeError):
        write_jsonl(
            target,
            [
                {"id": "new-1", "claim": "new snapshot"},
                {"id": "new-2", "not_json_serializable": object()},
            ],
        )

    assert target.read_bytes() == previous
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))


def test_successful_rewrite_replaces_complete_snapshot(tmp_path: Path) -> None:
    target = tmp_path / "memory" / "open_loops.jsonl"
    write_jsonl(target, [{"id": "old"}])

    write_jsonl(target, [{"id": "new-1"}, {"id": "new-2"}])

    assert read_jsonl(target) == [{"id": "new-1"}, {"id": "new-2"}]
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))
