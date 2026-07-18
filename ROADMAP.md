# Arova Roadmap — Phase 0: Productization & Beta

We have officially **frozen core architectural expansion** (`Phase 1–12` complete). Our sole focus for the next 3 weeks and beyond is turning our state-of-the-art cognitive infrastructure into a rock-solid, effortless desktop product validated by daily **Design Partners**.

---

## Phase 0: Ship Beta Checklist

### Week 1: One-Click Installer & Single-Process Management
- [ ] **Single Executable Packaging**: Configure Tauri build pipeline (`npm run tauri build`) to produce double-click installers (`.AppImage`, `.dmg`, `.exe`).
- [ ] **Daemon Auto-Start & Recovery**: When the desktop UI launches, automatically spawn `arovad` (`python -m arova.daemon.main`) in the background. Auto-create SQLite stores (`~/.arova/data/`) and auto-restart the daemon if it encounters an unhandled exception.
- [ ] **No-Terminal First Run**: Replace terminal environment setup (`venv`, `pip install`) with a clean 3-step UI modal:
  1. *Welcome to Arova*
  2. *Choose AI Provider* (`OpenAI`, `Groq`, or local `Ollama`)
  3. *Continue to Workspace*

### Week 2: Public Repository Polish & Diagnostics
- [ ] **Debug Report Export**: Add a one-click `Export Debug Report` button in Settings that bundles local runtime logs (`daemon.log`, `daemon_audit.log`, recent telemetry events) into a sanitized `.zip` for instant troubleshooting.
- [ ] **Repository Governance**: Establish public `CONTRIBUTING.md` standards and apply structured non-commercial/BSL licensing to protect core IP while welcoming open inspection.

### Week 3: Daily Design Partner Validation
- [ ] Onboard **5 Design Partners** across 4 key workflows:
  - **Developer**: Complex IDE, terminal, and documentation loops.
  - **Student**: Multi-PDF study and notes continuity.
  - **Writer**: Long-form drafting and structural revisions.
  - **Founder**: Cross-app operational continuity (Notion, Slack, Linear, pitch decks).
- [ ] Measure real behavioral outcomes:
  - **Context Recovery Time Saved** (`telemetry.context_recovery_saved`)
  - **Three-Second Scan Success** (Did they resume without opening a file explorer?)
  - **Decision Continuity Impact** (Did Arova prevent revisiting settled decisions?)

---

## Core Operational Goals (Next 6 Months)

Every single pull request or feature proposal must answer: *"Does this make Arova noticeably better at helping someone continue meaningful work?"*

1. **Resume Perfectly**: Give the user 20 minutes back every morning.
2. **Prepare Perfectly**: Automatically restore exact files, tabs, terminal directories, and settled decisions on resumption.
3. **Intervene Rarely**: One high-signal, effort-saving analytical insight every two days (`stuckness_score >= 75%`).
4. **Measure Real Outcomes**: Track empirical effort reduction, avoided context switches, and daily retention.
