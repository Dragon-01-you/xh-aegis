# Changelog

All notable changes to **芯火·灵镜 XH-Aegis (`xh-aegis`)** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-12

### Security / Trust
- Belief gate: model-supplied `override_state` and `confidence_delta` are ignored; new beliefs are always `HYPOTHESIS`; confidence steps come from `epistemic_rules`; promotion to `VERIFIED_PATTERN` requires confidence, >=3 distinct evidence episodes and >=2 calendar days; evidence IDs must exist; the same evidence cannot re-inflate confidence; deprecated beliefs cannot be revived.
- Topic names are sanitized (no path traversal); model text is flattened to one line before entering `working_memory.md` (no Markdown/instruction injection).
- Proactive hooks must anchor to a real commitment/belief, confidence is capped by the belief's real confidence, hooks expire (`hook_ttl_hours`), and the outreach prompt no longer receives the full working memory or latent inferences.

### Fixed
- REM/NREM: strict JSON validation (tolerates fences / `<think>`); invalid or empty output fails loudly without marking episodes processed or clearing the buffer; enum/ID validation for commitment updates; mid-run failure rolls back to the pre-REM snapshot.
- L0 buffer is persisted (`session_buffer.json`) and only consumed after a successful distillation.
- Foreground chat now sends recent history to the model.
- L2 retrieval uses tokenized overlap instead of a hard-coded demo keyword list (`go` no longer matches `good`).
- Git snapshots no longer hard-code `master` (broken under `init.defaultBranch=main`); REM takes pre/post snapshots; rollback appends history and can be repeated.
- Unanswered-strike counter and last-sent time persist; `cooldown_hours` is honored; quiet hours support non-wrapping windows; sent messages go to `outbox.jsonl` and L0 history.
- `mock_mode=False` without an API key raises instead of silently falling back to mock; per-tier `api_key_env` / `base_url`; retry on 429/5xx/timeouts.
- Atomic JSON writes; corrupt JSON is quarantined as `*.corrupt`; commitment de-duplication and monotonic IDs; `commitments_resolved` is validated and handed to REM instead of being dropped.
- `cli_demo` moved into the package (the installed `xh-aegis` command previously failed to import it); `--auto-demo` runs in a temp dir instead of overwriting `data/`; README math (tab-corrupted `\t` sequences) repaired.
- Runtime state under `data/` is no longer tracked (only `data/persona.md`).

### Added
- `tests/test_trust_and_reliability.py` (regression suite); CI now runs the whole `tests/` directory.

## [1.0.0] - 2026-11-07

### Added
- **Four-Tier Dual-Representation Memory Store (`xh_aegis/memory_store.py`)**: Implemented L0 session buffer, L1 deterministic `working_memory.md` compiler (hard-capped at `<= 160` lines), L2 structured `causal_beliefs.json` + `commitments.json` + `topics/*.md`, and L3 episodic archives.
- **Bio-Inspired NREM + REM Sleep Consolidation (`xh_aegis/sleep_cycle.py`)**: Decoupled lightweight episode distillation (`fast_tier`) from cross-day Say-Do alignment auditing and counterfactual causal inference (`deep_tier`).
- **5-State Epistemic State Machine (`xh_aegis/models.py`)**: Added `OBSERVATION -> HYPOTHESIS -> VERIFIED_PATTERN -> CONTESTED -> DEPRECATED` transitions with mandatory `falsification_condition` and `evolution_history`.
- **Utility-Gated Proactive Outreach Engine (`xh_aegis/proactive_engine.py`)**: Implemented $U_{\text{wake}} = V \times T \times C - \text{Cost}$ scoring, quiet hours (23:00–08:00), and unanswered strike circuit breaker.
- **Automated Git Cognitive Time Machine**: Every REM cycle automatically commits a `[REM-Cycle]` snapshot supporting one-command `/rollback`.
