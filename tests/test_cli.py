from pathlib import Path

from ahaos.incubation import incubate
from ahaos.storage_jsonl import load_memory_atoms, load_open_loops, validate_memory_dir
from ahaos.verification import filter_verified


def test_example_memory_valid():
    memory_dir = Path("examples/coding_agent_pr_review")
    assert validate_memory_dir(memory_dir) == []


def test_incubation_produces_verified_candidates():
    memory_dir = Path("examples/coding_agent_pr_review")
    atoms = load_memory_atoms(memory_dir)
    loops = load_open_loops(memory_dir)
    candidates = incubate(atoms, loops)
    verified = filter_verified(candidates)
    assert len(verified) >= 1
