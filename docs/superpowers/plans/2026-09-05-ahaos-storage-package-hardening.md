# AhaOS Storage and Package Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close F12 and F14 on exact `AhaOS@7b7cb283273af58c676a2dbdf0915f3ec881c75b`: JSONL rewrites must be atomic, and the published wheel must contain every runtime module needed by the `ahaos-checkpoint` console command.

**Architecture:** Keep the current APIs and pilot implementation. `write_jsonl` writes to a unique temporary file in the destination directory, flushes/fsyncs it, and atomically replaces the destination only after all rows serialize successfully. The existing `scripts.pilot` runtime dependency becomes an explicit Python package included in the wheel rather than moving or duplicating the pilot implementation.

**Tech Stack:** Python stdlib (`tempfile`, `os`, `json`), setuptools, pytest.

**Spec:** GitHub Portfolio Engineering Review 2026-09-05 findings F12 and F14 as independently re-audited against `AhaOS@7b7cb283273af58c676a2dbdf0915f3ec881c75b`.

## Constraints

- Preserve `write_jsonl(path, rows)` and `run_checkpoint(...)` public behavior.
- A failed JSON serialization must leave any pre-existing destination byte-for-byte unchanged.
- Temporary artifacts must be removed after success or failure.
- Use same-directory atomic replacement so the rename does not cross filesystems.
- Do not duplicate or move the existing pilot implementation in this phase.
- The built wheel must include the `scripts.pilot` dependency used by `ahaos.agent_memory`.
- Do not add/upgrade dependency requirements, alter CI, publish a package, push, create a PR, or mutate GitHub.

---

### Task 1: Establish baseline and add RED storage regression

**Files:**
- Create: `tests/test_storage_jsonl.py`

**Interfaces:**
- Consumes: `ahaos.storage_jsonl.write_jsonl`.
- Produces: regression proof that an interrupted/failed replacement preserves the previous snapshot.

- [ ] Create an existing valid JSONL snapshot.
- [ ] Attempt to replace it with a sequence whose later row is not JSON serializable.
- [ ] Assert the serialization exception is raised and the original bytes remain unchanged.
- [ ] Assert no temporary sibling remains.
- [ ] Run the focused test and verify RED on the current direct-`"w"` implementation.

### Task 2: Implement atomic JSONL replacement

**Files:**
- Modify: `ahaos/storage_jsonl.py`
- Test: `tests/test_storage_jsonl.py`

**Interfaces:**
- Same `write_jsonl(path, rows)` API.

- [ ] Create one `NamedTemporaryFile(delete=False)` under `path.parent`.
- [ ] Serialize/write all rows to the temporary file.
- [ ] Flush and `os.fsync()` before replacement.
- [ ] `os.replace(temp_path, path)` only after the entire stream succeeds.
- [ ] On any exception, unlink only the exact temporary file and re-raise.
- [ ] Add/retain a successful replacement test and verify focused GREEN.

### Task 3: Add RED package-closure regression

**Files:**
- Create: `tests/test_packaging.py`
- Create after RED: `scripts/__init__.py`
- Modify after RED: `pyproject.toml`

**Interfaces:**
- `ahaos-checkpoint = "ahaos.agent_memory:main"` continues to import `scripts.pilot` at runtime.

- [ ] Assert packaging config explicitly includes both `ahaos` and `scripts`.
- [ ] Assert `scripts` is an importable package with `pilot.py` present.
- [ ] Run the focused test and verify RED on the current `[tool.setuptools] packages = ["ahaos"]` config.
- [ ] Add the minimal package marker/config and verify focused GREEN.

### Task 4: Prove the actual wheel is self-contained for checkpoint runtime

**Files:**
- Verify packaging only; do not publish.

- [ ] Build a wheel locally with `python -m pip wheel . --no-deps` into a temporary directory.
- [ ] Inspect the wheel archive and require both `ahaos/agent_memory.py` and `scripts/pilot.py`.
- [ ] Install that wheel into a clean temporary virtual environment without the source checkout on `PYTHONPATH`.
- [ ] Run `ahaos-checkpoint --help` from outside the source tree and require exit 0.
- [ ] Import `scripts.pilot` from the installed environment and verify its path is inside site-packages, not the checkout.

### Task 5: Final verification

**Files:**
- Verify only `ahaos/storage_jsonl.py`, packaging files, tests, and this plan.

- [ ] Run the full `pytest` suite.
- [ ] Run `ruff check` on all Python files changed by this phase. Note that exact-base `ruff check .` already reports 28 unrelated pre-existing findings, so repository-wide lint is evidence only, not a newly satisfiable gate for this patch.
- [ ] Run `python -m compileall -q ahaos scripts tests`.
- [ ] Run `git diff --check`.
- [ ] Re-fetch `origin/master` and require exact `7b7cb283273af58c676a2dbdf0915f3ec881c75b` before declaring the local candidate review-ready.
- [ ] Record changed paths/diff; do not commit or push.
