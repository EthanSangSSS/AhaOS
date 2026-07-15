# Contributing to AhaOS

AhaOS welcomes contributions that improve evidence-backed insight generation for agents. This document outlines the PR workflow, test requirements, dependency guidelines, safety boundaries, and core architectural rules.

## Core Behavioral Guidelines

1. **Safety First**: Do not read secrets, credentials, SSH keys, browser data, raw private chat logs, or private memory dumps. Do not implement hosted telemetry, autonomous execution, or hosted database connectors.
2. **Local-first by default**: Do not add behavior that scans `$HOME`, browser profiles, token stores, unrelated local directories, or external services unless the user explicitly supplies a bounded path and the PR documents the boundary.
3. **Evidence before insight**: Treat generated insights as hypotheses until supported by source files, tests, logs, builds, git state, or other primary evidence.
4. **Minimal dependency footprint**: Do not add, remove, or upgrade any project dependencies, including dev/test packages, without explicit user or project-lead agreement. Implement built-in custom parsers using Python standard libraries when possible.
5. **Preserve documentation**: Maintain documentation integrity by preserving existing comments, docstrings, and help text unless specifically updating them.

---

## PR Workflow

1. **Fork and Clone**: Fork the repository and create a new feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Implement Changes**: Write clean, concise code following PEP 8.
3. **Verify Environment**: Ensure your virtual environment is active:
   ```bash
   .venv/bin/python -m pytest tests/ -v
   ```
4. **Write Tests**: Every new feature or bug fix must have matching tests in `tests/test_core.py`, `tests/test_pilot.py`, or a more specific test module.
5. **Lint and Format**: Run `ruff` when available:
   ```bash
   .venv/bin/ruff check .
   ```
6. **State evidence**: In the PR, paste exact command output or state that a command was not run. Do not claim PASS without evidence.
7. **Submit PR**: Open a Pull Request referencing the issue or feature you are implementing.

---

## Public-Safety Boundary

Do not include:

- secrets, tokens, SSH keys, browser data, raw private chat logs, or private memory dumps;
- private customer, employer, identity, medical, financial, or credential material;
- examples that imply AhaOS should autonomously execute actions;
- claims that an insight is verified without primary evidence;
- hosted telemetry, hosted memory sync, or external connector behavior without explicit design review.

Use synthetic or public-safe examples only.

---

## Testing Requirements

- **Zero regression policy**: All existing unit and integration tests must pass cleanly before claiming readiness.
- **Coverage**: New cognitive miners, config keys, or verification gate behaviors must be covered by unit tests.
- **Test execution**: Prefer the local virtual environment's pytest tool:
   ```bash
   .venv/bin/python -m pytest tests/
   ```
- **Fallback**: If the virtual environment is unavailable, report that limitation instead of substituting unverified claims.

---

## Cognitive Architecture Rules

When contributing to incubation mechanisms, ensure code adheres to the three-tier model:

1. **Preparation (Evidence & Confidence)**: Verify inputs have valid `evidence` and `confidence` properties.
2. **Incubation (Spreading Activation & Decay)**:
   - Apply Ebbinghaus forgetting curve decay (`salience_with_decay`) based on `last_seen_at` or `created_at` anchors.
   - Run tag-based Spreading Activation to find remote connections (hop count ≥ 2).
   - Track multi-cycle maturation history using `candidate_history` seen count.
3. **顿悟 (Insight/Illumination)**:
   - Rank and sort candidates using a boosted score combining surprise (structural distance), relevance (open loops), and activation/maturation counts:
     `final_score = base_score + 0.05 * log(1 + activation_count)`

---

## Suggested validation

```bash
.venv/bin/python -m pytest tests/
.venv/bin/ruff check .
python3 scripts/pilot.py --input-dir examples/local_pilot_input --work-dir /tmp/ahaos-local-pilot --report-dir /tmp/ahaos-local-pilot-reports --top-k 3 --dry-run
git diff --check
```

Only claim these commands passed when they actually ran and exact output is captured.
