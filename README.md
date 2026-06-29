# AhaOS

**AhaOS is an incubation-first insight layer for AI agents.**

Most agent memory systems help agents remember. AhaOS helps agents notice.

It turns passive memories, open loops, repeated failures, project history, and tool telemetry into rare, evidence-backed, cross-domain insights.

## What AhaOS is

AhaOS is not another vector database, hosted memory service, or autonomous action runner.

It is a local-first engine for generating:

- non-obvious connections
- reusable patterns
- contradiction alerts
- open-loop pressure signals
- time-incubated memory pressure
- incremental trigger signals
- negative-space gaps
- evidence-backed insight reports
- agent skills for reflection and reuse

## Core idea

An insight is not a summary.

| Output type | Question answered |
|---|---|
| Summary | What happened? |
| Reflection | What did we learn? |
| Insight | What hidden connection creates new leverage? |

AhaOS optimizes for the third one.

## The Aha Loop

```text
Observe
  -> Atomize
  -> Link
  -> Pressurize
  -> Incubate
  -> Compose
  -> Verify
  -> Deliver
  -> Learn
```

## Design principles

1. Insight is not recall.
2. Memory is evidence, not authority.
3. No actionable insight without evidence.
4. Low semantic similarity can still be high structural value.
5. Open loops create cognitive pressure.
6. Contradictions are first-class signals.
7. Delivery must be rare and useful.
8. Agent memory must be safe before it is powerful.

## Quickstart

```bash
git clone https://github.com/EthanSangSSS/AhaOS.git
cd AhaOS
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

ahaos init
ahaos run --memory-dir examples/coding_agent_pr_review --report-dir .ahaos/reports --top-k 3
```

## CLI

```bash
ahaos init
ahaos validate --memory-dir examples/coding_agent_pr_review
ahaos run --memory-dir examples/coding_agent_pr_review --report-dir .ahaos/reports --top-k 3
```

## Current scope

AhaOS v0.3 is an incubation-first insight layer.

### v0.3 includes:
- temporal metadata
- forgetting-curve salience decay
- activation heat
- spreading activation
- negative-space mining
- pilot trigger candidates
- candidate maturation
- local pilot state

## Local Pilot Quickstart

You can run the pilot to scan local directories for memories:

```bash
python3 scripts/pilot.py \
  --input-dir examples/local_pilot_input \
  --work-dir /tmp/ahaos-local-pilot \
  --report-dir /tmp/ahaos-local-pilot-reports \
  --top-k 3
```

To run without writing a report (dry-run):

```bash
python3 scripts/pilot.py \
  --input-dir examples/local_pilot_input \
  --work-dir /tmp/ahaos-local-pilot \
  --report-dir /tmp/ahaos-local-pilot-reports \
  --top-k 3 \
  --dry-run
```

## Agent Workflow Integration

AhaOS is most useful as an agent-side memory incubator, not as a replacement for an agent's working memory or for primary evidence. A practical integration pattern is to run it at three checkpoints:

1. **Preflight:** before complex multi-file work, release/signing/CI/cron changes, or workflow design, create a small explicit `/tmp` input bundle with the current goal, constraints, known risks, and relevant local notes. Inspect AhaOS output for historical traps, protected scopes, and reusable prior patterns.
2. **Mid-flight:** after repeated failures or surprising behavior, add the failing commands, observations, and candidate causes as JSONL or Markdown notes. Use `trigger_candidates.jsonl` to see whether the new evidence reactivates older dormant memories.
3. **Final reflection:** before commit/push or handoff, review `aha_candidates.jsonl` and `latent_links.jsonl` for unclosed risks and reusable lessons. Promote only verified findings into AGENTS.md rules, skills, SOPs, or checklists.

Treat AhaOS outputs as hypotheses. Validate them with source files, tests, logs, builds, git state, and other primary evidence before acting. Do not feed secrets, env files, SSH keys, token files, browser profiles, or broad `$HOME` scans into the pilot.

## Non-goals

AhaOS does not:

- execute actions autonomously
- read secrets
- send webhooks/emails/messages
- replace Mem0, Letta, Zep, Graphiti, LangMem, or vector databases
- claim to reproduce human cognition

AhaOS is the missing incubation layer between agent memory and agent action.

## Repository structure

```text
ahaos/
  models.py          # typed schema dataclasses
  storage_jsonl.py   # local JSONL loading and validation
  pressure.py        # open-loop, salience, and age-boost scoring
  incubation.py      # pattern / contradiction / reuse / negative-space mining
  verification.py    # evidence and safety gates
  report.py          # Markdown report generation
  cli.py             # command line interface

docs/
  concept.md
  architecture.md
  safety_model.md
  evaluation.md

scripts/
  pilot.py           # explicit local input pilot with trigger candidates

skills/
  codex/ahaos-insight-engine/SKILL.md
  claude/ahaos-insight-engine/SKILL.md
```

## License

MIT.
