# Changelog

All notable changes to **芯火·灵镜 XH-Aegis (`xh-aegis`)** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-07

### Added
- **Four-Tier Dual-Representation Memory Store (`xh_aegis/memory_store.py`)**: Implemented L0 session buffer, L1 deterministic `working_memory.md` compiler (hard-capped at `<= 160` lines), L2 structured `causal_beliefs.json` + `commitments.json` + `topics/*.md`, and L3 episodic archives.
- **Bio-Inspired NREM + REM Sleep Consolidation (`xh_aegis/sleep_cycle.py`)**: Decoupled lightweight episode distillation (`fast_tier`) from cross-day Say-Do alignment auditing and counterfactual causal inference (`deep_tier`).
- **5-State Epistemic State Machine (`xh_aegis/models.py`)**: Added `OBSERVATION -> HYPOTHESIS -> VERIFIED_PATTERN -> CONTESTED -> DEPRECATED` transitions with mandatory `falsification_condition` and `evolution_history`.
- **Utility-Gated Proactive Outreach Engine (`xh_aegis/proactive_engine.py`)**: Implemented $U_{\text{wake}} = V \times T \times C - \text{Cost}$ scoring, quiet hours (23:00–08:00), and unanswered strike circuit breaker.
- **Automated Git Cognitive Time Machine**: Every REM cycle automatically commits a `[REM-Cycle]` snapshot supporting one-command `/rollback`.
