# Architecture

AhaOS follows the Aha Loop:

```text
Observe -> Atomize -> Link -> Pressurize -> Incubate -> Compose -> Verify -> Deliver -> Learn
```

## Observe

Read explicit local events: Markdown, JSONL, Git logs, PR summaries, CI logs, or manual notes. The agent checkpoint path accepts only agent-provided task summaries and persists them in a project namespace; it does not ingest raw chat histories.

## Atomize

Convert events into small durable memory atoms. Deterministic Chinese aliases normalize common release, validation, rollback, workflow, and failure language into portable tags; explicit procedural language becomes a `procedural` atom instead of a generic semantic note.

## Link

Connect atoms through tags, projects, evidence, relation hints, and explainable structural slots. The local pilot currently extracts lightweight `problem`, `constraint`, `action`, `evidence`, and `open_loop` slots so distant memories can connect through shape, not only shared words.

## Pressurize

Prioritize unresolved loops, repeated failures, user priorities, cross-project reuse potential, and incubation age. Memory atoms and open loops may carry `created_at`, `last_seen_at`, `last_triggered_at`, and `activation_count`; older unresolved items receive a capped age boost over days. A full scan does not refresh `last_seen_at`; only a new or reactivated atom does.

## Incubate

Generate candidate insights using deterministic operators:

- pattern mining
- contradiction mining
- reuse mining
- open-loop pressure mining
- negative-space mining

Novelty is computed from evidence, project spread, incubation age, and structural distance rather than using a single fixed score.

## Trigger

The local pilot persists `state.json` under its work directory. On later runs, newly seen atoms act as triggers that can reactivate older atoms. Triggered candidates are written to `trigger_candidates.jsonl`, while weaker links remain in `latent_links.jsonl`.

## Verify

Reject candidates without evidence, with excessive risk, or with model inference as the only support. Pattern, contradiction, negative-space, and spreading-activation claims also require two independent evidence references.

## Deliver

Output rare, actionable, evidence-backed Markdown reports. Checkpoint runs additionally record candidate counts and later human feedback so usefulness can be measured instead of assumed.
