# Evaluation

AhaOS should be evaluated as an insight engine, not as a retrieval system.

## Benchmark tasks

- Hidden Bridge: detect low-similarity but structurally similar memories.
- Delayed Relevance: identify when an old memory becomes useful for a new task.
- Contradiction Catch: detect when a new verified event supersedes an old memory.
- Reuse Opportunity: find a reusable checklist, skill, or module.
- Failure Pattern: derive a procedural fix from repeated failures.
- False Insight Suppression: reject unsupported insights.
- Poisoned Memory Resistance: avoid accepting malicious or untrusted memories.

## Metrics

- Insight@K
- Useful@K
- Evidence precision
- Novelty score
- Actionability score
- False insight rate
- Contradiction detection rate
- Poisoned memory acceptance rate
- Interruption regret
