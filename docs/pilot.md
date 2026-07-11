# Pilot

`scripts/pilot.py` runs the existing AhaOS validation, incubation, verification, and report rendering pipeline against explicit local input files. It does not call external APIs or LLMs.

> [!NOTE]
> **AhaOS is NOT an operating system.** It does not replace the agent's main memory. Instead, it serves as a **memory incubator** that captures, mines, and reinforces the agent's fleeting moments of inspiration (aka "aha moments").

## Usage

```bash
python3 scripts/pilot.py \
  --input-dir examples/pilot_input \
  --work-dir /tmp/ahaos-work \
  --report-dir /tmp/ahaos-reports \
  --top-k 3
```

Use `--dry-run` to print the generated Markdown report instead of writing a report file. Even during a dry-run, temporary memory files, candidate lists, and latent links will still be written to the designated `--work-dir`.

## Input Rules

The pilot only reads `.md`, `.txt`, and `.jsonl` files under the explicit `--input-dir`. It refuses to scan `$HOME`, skips hidden files and hidden directories, and skips credential-like paths including `.env`, `.pem`, `.key`, `.ssh`, `.config`, `.git`, browser, token, secret, password, credential, and auth names.

Markdown and text inputs are converted into conservative memory atoms with `local_file` evidence, `first_party_file` trust, confidence `0.7`, and deterministic tags inferred from visible English keywords, explicit tags, and common Chinese task concepts. Explicit procedural language is classified as `procedural`; JSONL rows that already look like AhaOS memory atoms or open loops are accepted.

## Generated Files

Temporary memory files are written to `--work-dir`, which defaults to `/tmp/ahaos-work`.
- `atoms.jsonl`: Parsed active memory atoms.
- `open_loops.jsonl`: Parsed open loops.
- `state.json`: Records last seen atom/loop IDs plus `created_at`, `last_seen_at`, `last_triggered_at`, and `activation_count` metadata to support incubation and incremental trigger mode.
- `trigger_candidates.jsonl`: Filtered candidates triggered by newly added atoms in the current run.
- `aha_candidates.jsonl`: Contains evidence-backed but not necessarily verified inspiration candidates.
  - Core fields: `id`, `title`, `hypothesis`, `association_type`, `source_atom_ids`, `evidence_refs`, `aha_score`, `status`, `boundary`, `next_smallest_check`, and `triggered_by_atom_ids` (if triggered).
  - Open-loop candidates also include `source_loop_ids`.
- `latent_links.jsonl`: Represents weaker, potential connections between memories and loops.
  - Core fields: `id`, `reason`, `association_type`, `source_atom_ids`, `score`, `status`, and `triggered_by_atom_ids` (if triggered).
  - Open-loop links also include `source_loop_ids`.

Reports are written to `--report-dir`, which defaults to `/tmp/ahaos-reports`.

The report still comes from the core AhaOS `incubate -> verify -> render` path. The pilot's `aha_candidates.jsonl` and `latent_links.jsonl` files are an incubator side channel: they preserve weaker "aha moment" material for inspection and future promotion, but they are not automatically delivered as verified report insights.

### Association Heuristics
The pilot supports multiple association heuristics to map latent links and candidates:
1. `repeated_tag`: Activates when two or more memory atoms share the same tag.
2. `structural_echo`: Discovers structural similarity. Rather than only using common words, it extracts explainable pattern slots (`problem`, `constraint`, `action`, `evidence`, `open_loop`) to match structural isomorphism. Output items include `shared_structure` and `structural_distance` fields.
3. `open_loop_bridge`: Connects active open loops with memory atoms that might resolve them, based on explicit linkage, shared tags, or keyword overlap.

### Advanced Mechanisms
1. **Time/Activation Fields & Age Boost**: Memory atoms and open loops track `created_at`, `last_seen_at`, `last_triggered_at`, and `activation_count`. A time-based `age boost` increases over days for older unresolved atoms and loops, capped at `0.2`; a full scan does not reset the dormancy clock.
2. **Dynamic Novelty Calculation**: Instead of hardcoded values, novelty is computed dynamically based on the number of projects, evidence, age, and structural distance (Jaccard distance).
3. **Negative Space Mining**: Automatically mines "negative space" when multiple active memory atoms care about a tag/topic but lack a corresponding `procedural` or `decision` type solution.
4. **Incremental Trigger Mode**: Preserves state in `work-dir/state.json`. After the first run, newly added atoms act as trigger atoms. Candidates and links that contain triggers annotate `triggered_by_atom_ids`, prioritize "new atom activating old atom" by boosting score, update activation metadata for reactivated older atoms, and get collected in `trigger_candidates.jsonl`.

## Rollback

The pilot does not modify the source input directory. To remove generated output:

```bash
rm -rf /tmp/ahaos-work /tmp/ahaos-reports
```

If you used custom directories, remove those custom `--work-dir` and `--report-dir` paths instead.
