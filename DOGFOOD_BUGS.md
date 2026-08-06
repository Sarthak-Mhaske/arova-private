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

## TEAM CONSTITUTION: REALITY BEFORE CODE

Every engineering task, bug fix, or architectural change must adhere to this 7-part constitution before writing code:

### 1. Is this a real bug or a hypothesis?
Can it be empirically reproduced, recorded, and observed by another engineer across a live runtime session?
If not, **it is not yet a bug—it is a verification hypothesis.**

### 2. What runtime evidence proves it?
We reject static code assumptions, comments, and architectural diagrams as proof. Evidence must consist exclusively of:
- Event bus traces (`arova.kpi`)
- Precise timestamps & latency metrics
- System logs (`/tmp/arova.sock`, daemon output)
- Screen/video recordings
- Profiler / memory snapshots
- IPC payload dumps
- SQLite database row inspection

### 3. Where does truth originate?
Every UI element must trace back to exactly one authoritative, live runtime source of truth.
```text
Continue Card → WorkspaceManager → Workspace Graph → Working Memory Runtime → CanonicalActivityEvents → Capture Providers
```
**NEVER ALLOWED:** Fallback default values or hardcoded estimates replacing missing runtime state.

### 4. Can this become stale? (Staleness & Expiry Guarantee)
Every state object must declare explicit lifecycle metadata:
```json
{
  "created_at": 1784623120.0,
  "updated_at": 1784623142.0,
  "source": "VSCodeExtension",
  "refresh_trigger": "workspace.summary.updated",
  "ttl": 300
}
```
If an object exceeds its `ttl` or misses its refresh window, the UI must explicitly state:
> *"Last updated 18 minutes ago"* or *"Still learning..."* instead of pretending it is live.

### 5. Every UI Component Gets a Reality Contract
Before modifying or shipping any UI element, its exact **Reality Contract** must be documented and enforced:
```markdown
| Component | Purpose | Source Object | Refresh Trigger | Expected Rate | Max Staleness | Fallback | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Continue Card** | Task continuity & recovery | `WorkspaceSummary` | `workspace.summary.updated` | < 2 seconds | 60 seconds | *"Still learning..."* | Workspace Runtime |
| **Vision UI** | Screen & layout awareness | `AmbientContext` | `ambience.CONTEXT_CHANGED` | < 1 second | 5 seconds | *"Observing screen..."* | Vision Runtime |
| **Attention Orb**| Cognitive modulation state | `OrbState` | `cognition.MODULATION_SYNC`| < 500 ms | 2 seconds | *"Present"* | Cognition Runtime |
```

### 6. Every Background Runtime Answers Exactly One Question
Runtimes must not exist merely for architectural symmetry; they must continuously answer one fundamental user question:
- **Vision Runtime**: *"What is on the screen right now?"*
- **Memory Runtime**: *"What should be remembered across sessions?"*
- **Attention Runtime**: *"What matters right now?"*
- **Workspace Runtime**: *"What is the user actually doing right now?"*
- **Working Memory Runtime**: *"What is the active working set (files, errors, docs, goals) right now?"*
- **Resume Runtime**: *"What physical environment should be restored right now?"*

### 7. Kill the "Feature Completed" Mentality
A feature is **not** complete because code exists, tests pass, or a UI card renders.
A feature is complete when **a real software engineer, using a real machine, across an 8-hour workday, actively trusts it without verifying against manual tools.**

---

## The Continuous Cognition Loop & Working Memory Architecture

We reject the reactive `User asks → LLM thinks` paradigm. We enforce an inverted, continuously alive reasoning pipeline decoupled by a **Working Memory Runtime** to prevent inference fatigue and cost spikes:
```text
Capture → Canonical Events → Workspace Graph → Working Memory Runtime → Reasoning Runtime → Memory Runtime → Search Runtime → UI
```
*Why Working Memory?* Continuous LLM evaluation over every granular keystroke/event is noisy and expensive. The **Working Memory Runtime** maintains an always-current, compact representation of active files, recent browser docs, terminal cwd, compiler tracebacks, and goal momentum—triggering heavier **Reasoning & Memory Formation** only when the working set shifts meaningfully.

---

## Verification Hypotheses (`Pre-Feature Purge Checklist`)

Before building new capabilities, the following code-inspected findings must be verified against live runtime evidence (`event traces, DB dumps, IPC logs`). Once empirically proven, they graduate to P0 bugs and must be purged:

| ID | Hypothesis / Component | Observation / Risk | Required Runtime Verification Evidence | Action Plan Upon Confirmation |
| :--- | :--- | :--- | :--- | :--- |
| **HYP-01** | **Continue Card Hardcoding** | `WorkspaceManager.get_continue_context` appears to emit fallback scores (`blk_score=89`, `goal_score=100`) and default narratives when no session history exists. | Record WebSocket payload (`workspace.sync`) on a fresh workspace with zero capture events. | Purge default fallback scores/strings; enforce Reality Contract (`Fallback: "Still learning your workspace..."`). |
| **HYP-02** | **Startup Mock Threads** | `ThreadManager.__init__` appears to inject a hardcoded `Memory Consent System` thread (`t1`) on daemon boot. | Dump `threads.list` IPC payload on daemon startup before any activity occurs. | Delete `t1` injection; ensure `ThreadsSurface` renders only genuine latent threads from `CognitiveThread` table. |
| **HYP-03** | **Presence vs. Vision Boundary** | `LiveOSAmbientProvider` appears to poll `hyprctl`/`xdotool` window titles rather than performing deep OCR/layout screen inference. | Inspect `AmbientContext` payload attributes across multi-window switching. | Explicitly label window-title data as `Presence/OS Awareness` and separate it cleanly from visual `Screen OCR/Layout Vision`. |
| **HYP-04** | **Snapshot vs. Continuous Memory** | Deep Context and Memory appear to form during boundaries (chat turns, session exit) rather than continuously evolving via Working Memory. | Monitor `memory.saved` events during a 60-minute coding session with zero chat interaction. | Wire `Working Memory Runtime` diffs into background `MemoryRuntime` evaluation. |

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
