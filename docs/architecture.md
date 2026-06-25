# Architecture

AhaOS follows the Aha Loop:

```text
Observe -> Atomize -> Link -> Pressurize -> Incubate -> Compose -> Verify -> Deliver -> Learn
```

## Observe

Read events from local sources: Markdown, JSONL, Git logs, PR summaries, CI logs, or manual notes.

## Atomize

Convert events into small durable memory atoms.

## Link

Connect atoms through tags, projects, evidence, and relation hints.

## Pressurize

Prioritize unresolved loops, repeated failures, user priorities, and cross-project reuse potential.

## Incubate

Generate candidate insights using deterministic operators:

- pattern mining
- contradiction mining
- reuse mining
- open-loop pressure mining
- negative-space mining

## Verify

Reject candidates without evidence, with excessive risk, or with model inference as the only support.

## Deliver

Output rare, actionable, evidence-backed Markdown reports.
