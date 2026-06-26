# Changelog

All notable changes to AhaOS will be documented in this file.

## [0.3.0] - 2026-06-27

### Added
- **Ebbinghaus Forgetting Curve**: Implemented temporal salience decay (`salience_with_decay`) based on time since memory atoms were last seen, with a protective floor of `0.3`.
- **Spreading Activation**: Added BFS-based N-hop spreading activation (`mine_spreading_activation`) in the tag similarity graph to discover remote latent associations (hop count ≥ 2).
- **Maturation Boost & Promotion**: Implemented memory candidate maturation tracking. Candidates seen multiple times are boosted and promoted from local pilot heuristics to standard verified insights.
- **Richer Structural Isomorphism**: Expanded `extract_structural_signature` with 9 slots including `trigger_condition`, `target_artifact`, `outcome`, and `frequency`.
- **Negative-Space Mining**: Automatically detects tags that are referenced across active memories but lack any procedural or decision guidance.
- **Local Config Parsing**: Implemented a zero-dependency lightweight YAML parser in `ahaos/config.py` to parse `.ahaos/config.yaml` for safety and delivery thresholds.
- **Content-Level Secret Filtering**: Skipping lines matching common API keys/tokens (`sk-`, `ghp_`, `AKIA`, private keys, client secrets, etc.) during local scanning to prevent leakage.
- **Hardened Evidence Gate**: Default run and pilot behaviors require evidence validation. Disabling this requirement now requires an explicit CLI flag `--unsafe-allow-no-evidence`.

### Changed
- Renamed project directories and scripts from `AhaOS-local-pilot` / `local_pilot` to `AhaOS` / `pilot` for naming consistency.
- Updated default work directory to `/tmp/ahaos-work` and reports directory to `/tmp/ahaos-reports` (with tests still supporting `/tmp/ahaos-local-pilot` paths).
