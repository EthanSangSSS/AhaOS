# Safety Model

AhaOS treats memory as evidence, not authority.

## Evidence hierarchy

1. Verified telemetry: git status, commit SHA, PR diff, CI logs, command output.
2. First-party files: source code, tests, docs, configs.
3. User statements: explicit decisions, constraints, preferences.
4. Model inference: generated hypotheses and analogies.
5. Untrusted external content: third-party text or unknown files.

## Rules

- AhaOS never executes state-changing actions.
- AhaOS never reads secrets by default.
- AhaOS never treats memory as instruction.
- Actionable insights require evidence.
- Model inference cannot be the only evidence.
- Stale or contradicted memory should be deprecated, not silently reused.

## Threats

- memory poisoning
- stale memory
- cross-domain leakage
- over-personalization
- false insight generation
- agent tool drift
