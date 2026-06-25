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

AhaOS v0.1 is intentionally small:

- JSONL storage
- local-first execution
- no cloud dependency
- no external API calls
- open-loop tracking
- pattern mining
- contradiction mining
- reuse mining
- evidence gate
- Markdown report generation
- Codex / Claude skill templates

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
  pressure.py        # open-loop and salience scoring
  incubation.py      # pattern / contradiction / reuse mining
  verification.py    # evidence and safety gates
  report.py          # Markdown report generation
  cli.py             # command line interface

docs/
  concept.md
  architecture.md
  safety_model.md
  evaluation.md

skills/
  codex/ahaos-insight-engine/SKILL.md
  claude/ahaos-insight-engine/SKILL.md
```

## License

MIT.
