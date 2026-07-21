# Arova Reliability Phase Bug Tracker (`Phase 7 Reliability & Operational Readiness`)

> **MANDATORY TEAM DOGFOODING & RELIABILITY RULE:**
> **No new abstractions without evidence. From now on every architectural change must originate from a bug.**
> **You're not allowed to manually search first. You must ask Arova first.**
> If it fails or forces you to fall back to manual VS Code / Chrome search, that is a bug and must be logged here.

Keep this file updated during our 2–3 week dogfooding sprint. Log real bugs observed when living inside Arova and breaking it across real developer workflows.

---

## Reliability Phase Quantitative Exit Criteria (`Scorecard`)

While design correctness is proven (`42/42 tests passing`, zero fake UI paths, clean layer separation), production readiness is determined by **quantitative operational reliability**. We must satisfy the following scorecard before declaring Arova ready:

| Metric | Target | Status |
| :--- | :--- | :--- |
| **Crash-free sessions** | ≥ 99% | 🟡 Monitoring |
| **Successful workspace restores** | ≥ 95% | 🟢 Verified (Unit + Integration) |
| **Time to First Productive Action** | Median < 30s, P95 < 60s | 🟡 Monitoring |
| **IPC reconnect success** | 100% | 🟡 Audit Scheduled |
| **Memory growth** | < 5–10% over an 8-hour session (excluding caches/models) | 🟡 Monitoring |
| **Event ordering failures** | 0 duplicated, dropped, or out-of-order events | 🟡 Audit Scheduled |
| **Unhandled exceptions** | 0 | 🟢 Verified across tests / monitoring |
| **Regression tests added** | 1+ for every production bug where practical | 🟢 Active Requirement |

---

## Bug Severity Taxonomy & Release Gate Rules

To maintain momentum and prevent cosmetic polish from delaying core stability work, all issues logged during dogfooding must be assigned a strict priority level:

- **P0 (Critical)**: Data loss, crashes, corrupted workspace, restore failure.
- **P1 (High)**: Core workflow interruption (Resume, Search, Capture, IPC disconnection).
- **P2 (Medium)**: UX friction, performance regressions, incorrect UI state.
- **P3 (Low)**: Cosmetic or polish issues.

### Release Gate Rules
- 🛑 **No open P0 bugs.**
- 🛑 **No unresolved P1 bugs older than one week.**
- ✅ **P2/P3 can ship if documented.**

---

## The Operational Quality Loop

We strictly follow this closed-loop engineering process for all modifications:

```text
Dogfood → Reproduce → Root Cause → Minimal Fix → Regression Test → Close Issue
```

> *Every bug fix must include an automated regression test whenever practical to ensure quality continuously increases rather than oscillating.*

---

## Operational Telemetry & Success Rate Tracking

We track both latency/resource metrics and **success rate ratios** via structured logging (`arova.kpi`) during daily sessions:

### Success Rate Ratios (Quality Indicators)
- **Resume Success Rate**: Resume attempted vs. resume completed successfully.
- **Search Click-Through Rate**: Search queries where the first result was actually opened.
- **Launch Intent Acceptance**: Restore intents accepted vs. dismissed.
- **IPC Reconnection Ratio**: IPC reconnect attempts vs. successful reconnections.
- **Tool Execution Reliability**: Tool execution success vs. failure.

### Operational Resource Timings
- **Startup time & Workspace restore duration**
- **Average LLM response latency & Voice runtime latency**
- **Memory usage & thread count lifecycle over 8+ hour sessions**

---

## Production Hardening Audit Log

```text
2026-07-21
✅ RESOLVED: RestorationEngine bypassed universal platform contracts (`restoration_engine.py`)
Severity: High (Architecture violation)

Root cause:
EnvironmentRestorationEngine previously executed `subprocess.Popen` directly for VS Code, folders, and browser URLs (`shutil.which("code")`, `shutil.which("google-chrome")`), violating the universal `PlatformBackend` facade and `IntentExecutor` policy execution layer.

Fix:
Refactored `restoration_engine.py` to route 100% of resource restoration intents (`source_file`, `repository`, `terminal`, `webpage`) through `self.executor.execute_single(intent, self.backend, self.affinity)`. Removed all `subprocess` and `shutil` usage from the cognitive layer.

Verified:
Passed all 42 unit tests. Multi-file + repository code restoration cleanly delegates to `LinuxBackend` / `LinuxLauncher` via unified window intents (`VS Code`), maintaining zero architecture drift.
```

```text
2026-07-21
✅ RESOLVED: Inspector surface displayed simulated DAG / test graph data (`execution.py`, `attention.py`)
Severity: Medium (Production Readiness violation: "No fake data")

Root cause:
`ExecutionView` and `AttentionView` in `arova/desktop/ui/inspector/` previously generated hardcoded simulated graph nodes and placeholder metric readouts when displayed.

Fix:
Wired `ExecutionView` directly to live IPC payload transitions (`DAG_EXECUTION_STATE`, `COGNITIVE_STREAM_STATE`, `TASK_COMPLETE`) to render real cognitive task nodes and edges. Updated `AttentionView` readouts and progress bars to display real-time telemetry from `ATTENTION_STATE_CHANGED`.

Verified:
All inspector components cleanly process JSON payload streams without mock fallback data.
```

```text
2026-07-21
✅ RESOLVED: Chat surface simulated response timers instead of sending IPC payloads (`chat_surface.py`, `scheduler.py`, `main.py`)
Severity: High (IPC wiring gap)

Root cause:
`ChatSurface._send_message` previously ran a 1-second `GLib.timeout_add` timer that returned `"Cognitive processing complete. Simulated response generated for debugging."` instead of sending real user prompts over the UNIX domain socket (`/tmp/arova-desktop.sock`).

Fix:
Added `send_ipc_payload` to `UIScheduler` (`scheduler.py`) and bound it to `ArovaViewModel`'s `asyncio` UNIX socket writer in `desktop/main.py`. Updated `ChatSurface` to transmit `{ "type": "USER_PROMPT", ... }` payloads directly to the runtime daemon.

Verified:
All 42 unit tests pass (`test_platform_services`, `test_capture_engine`, etc.).
```

```text
2026-07-21
✅ RESOLVED: RuntimeProjector returned hardcoded placeholder strings (`projector.py`)
Severity: Medium (Production Readiness violation: "No fake data")

Root cause:
`RuntimeProjector.project_environment` and `project_system` previously returned `"dev-machine-01"`, `8`, and static `"GNOME/X11"` strings regardless of the host OS environment.

Fix:
Updated `RuntimeProjector` to project real environment variable state (`USER`, `LOGNAME`, `XDG_SESSION_TYPE`, `WAYLAND_DISPLAY`, `WSL_DISTRO_NAME`), real CPU count via `os.cpu_count()`, active thread counts via `threading.active_count()`, and live application focus state.

Verified:
Projections dynamically reflect real system environment attributes.
```

---

## Active & Remaining Dogfooding Observations

```text
2026-07-21
🔍 OPEN: Remaining temporary artifacts / TODO placeholders in runtime and orchestration layers (`runtime.py`, `orchestrator.py`)
Severity: Medium

Observation:
During production audit, minor diagnostic placeholders or temporary scaffolding patterns remain in non-core orchestration routines (`arova/runtime.py`, `arova/core/cognition/orchestrator.py`). Per frozen architecture principles, these should be systematically audited during live dogfooding as developer pain points arise.

Next Action:
Continue 7–10 day dogfooding sprint. Log any real-world workflow frictions or edge-case failures when interacting with multi-window IDE setups across Linux, macOS, and Windows.
```

---
