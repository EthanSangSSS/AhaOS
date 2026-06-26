# Contributing to AhaOS

AhaOS welcomes contributions that improve evidence-backed insight generation for agents. This document outlines the PR workflow, test requirements, dependency guidelines, and core architectural rules.

## Core Behavioral Guidelines

1. **Safety First**: Do not read secrets or credentials unless explicitly requested. Do not implement hosted telemetry, autonomous execution, or hosted database connectors.
2. **Minimal Dependency foot-print**: Do not add, remove, or upgrade any project dependencies (including dev/test packages) without explicit user or project-lead agreement. Implement built-in custom parsers (e.g., config parsing) using Python standard libraries when possible.
3. **Preserve Documentation**: Maintain documentation integrity by preserving all existing comments, docstrings, and help text unless specifically updating them.

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
4. **Write Tests**: Every new feature or bug fix must have matching tests in `tests/test_core.py` or `tests/test_pilot.py`.
5. **Lint and Format**: Run `ruff` to ensure compliance with the style guide:
   ```bash
   .venv/bin/ruff check .
   ```
6. **Submit PR**: Open a Pull Request referencing the issue or feature you are implementing.

---

## Testing Requirements

- **Zero regression policy**: All existing unit and integration tests must pass cleanly.
- **Coverage**: New cognitive miners, config keys, or verification gate behaviors must be covered by unit tests.
- **Test execution**: Always run tests using the local virtual environment's pytest tool:
   ```bash
   .venv/bin/python -m pytest tests/
   ```

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
