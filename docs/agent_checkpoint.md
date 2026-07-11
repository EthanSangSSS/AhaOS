# Agent Checkpoint Loop

The checkpoint loop turns AhaOS from an occasional manual report into a bounded local memory workflow:

```text
explicit task summary -> structured event -> persistent project state -> pilot -> verified report -> feedback -> metrics
```

It is intentionally a sequential workflow. The agent supplies a small, non-sensitive summary; AhaOS then runs deterministically and the agent verifies any candidate before acting.

## Commands

Use the source-tree command without installing any additional dependency:

```bash
python3 scripts/agent_checkpoint.py checkpoint \
  --project "$PWD" \
  --stage midflight \
  --goal "Resolve a repeated build failure" \
  --observation "The same native asset validation failed in two projects." \
  --open-loop "Identify the shared preflight check" \
  --priority P1
```

Stages are `preflight`, `midflight`, and `final`. The command writes only explicit `--goal`, `--observation`, and `--open-loop` values. It rejects empty or secret-like values and does not inspect raw agent histories, repositories, or the home directory.

On macOS, the default root is `~/Library/Application Support/AhaOS`. Each project gets a stable hashed namespace containing:

- `input/events.jsonl`: captured atoms and open loops
- `work/`: pilot state and candidate side-channel artifacts
- `reports/`: verified Markdown reports
- `runs.jsonl`: candidate, trigger, and delivered-insight counts
- `feedback.jsonl`: `accepted`, `rejected`, `verified`, or `helped` outcomes

## Trigger Policy

Run one checkpoint only when at least two of these signals apply:

- work spans multiple files, projects, or a known recurring workflow
- release, signing, CI, cron, deployment, or final-delivery risk exists
- a command or approach has failed repeatedly
- the task is designing or changing an agent workflow
- a final review can produce a reusable rule, skill, or checklist

Do not run it for simple edits, direct answers, or routine one-file changes. The output is a hypothesis queue, not authority.

## Feedback And Evaluation

Record feedback after a candidate is checked:

```bash
python3 scripts/agent_checkpoint.py feedback \
  --project "$PWD" \
  --candidate-id cand_example \
  --verdict verified \
  --note "Source and tests confirmed the candidate."

python3 scripts/agent_checkpoint.py metrics --project "$PWD"
```

The first operational evaluation should replay 30-50 completed qualifying tasks with and without checkpoints. Compare Useful@3, independently verified insights, false interruptions, time overhead, and whether a candidate changed a final decision or produced a reusable asset.
