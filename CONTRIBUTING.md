# Contributing to Arova

Welcome! Arova is **Persistent Working Memory** designed to eliminate the daily Context Reconstruction Tax for knowledge workers. We are currently in **Phase 0 — Ship Beta**, working closely with daily **Design Partners**.

---

## The Golden Rule for All Contributions

Before submitting a pull request, proposing a feature, or writing code, ask:
> **"Does this make Arova noticeably better at helping someone continue meaningful work or recover their context faster?"**

If the answer is not an immediate **YES**, it does not belong in the current release cycle. We do not accept PRs that add abstract cognitive layers, complex UI configuration screens, or generic chatbot wrappers.

---

## Architecture Freeze & Principles

1. **Core Abstractions are Frozen**: Do not add new backend layers alongside `RealityLayer`, `InterpretationLayer`, `UnderstandingLayer`, or `ConfidenceLayer`.
2. **Zero-Terminal User Experience**: The user should never have to open a terminal, set up a virtual environment, or run `pip install`. All runtime setup and recovery must be handled automatically by the single-process Tauri/Daemon manager.
3. **Quiet by Default**: Interventions (`surfacing_push`) must strictly respect backoff limits (`stuckness_score >= 75%`, 10+ minute cooldowns).
4. **Behavioral Telemetry Only**: Do not hardcode marketing metrics. Any effort-savings claim must be calculated directly from observed behavior (`resource_count`, `switches_avoided`, `context_recovery_saved`).

---

## Local Development Setup

1. **Python Backend**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -e .
   pytest tests/ -v
   ```

2. **Frontend & Tauri Shell**:
   ```bash
   cd frontend
   npm install
   npm run build
   ```

---

## License & Legal

By contributing to Arova, you agree that your contributions are subject to the project's **Business Source License (BSL)** / **PolyForm Noncommercial** terms as defined in `LICENSE`. Thank you for helping us build working memory for the world's knowledge workers!
