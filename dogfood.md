# Arova Dogfooding & Phase 1 Execution Ledger

============================================================
PHASE 1 FOCUS: Make Arova something YOU can't live without (1-2 weeks)
THE ONE TESTER QUESTION: "What did Arova remember that you had forgotten?"
============================================================

## Daily KPI Board (Visible Targets)

| KPI                        | Goal                  | Current Status |
| -------------------------- | --------------------- | -------------- |
| Install success            | >95%                  | Tracking       |
| Crash-free sessions        | >99%                  | Tracking       |
| Resume Success Rate        | Increasing every week | Tracking       |
| Manual search after resume | Decreasing            | Tracking       |
| Feedback marked "Perfect"  | Increasing            | Tracking       |
| "I'd keep this installed"  | >80% of testers       | Tracking       |

---

## 🛠️ Day 1: Arch Validation & Ugly Case QA Protocol

### 1. Native Installation & First Launch (Arch Linux)
- [ ] Package installs cleanly without missing dependencies (`pacman`/AppImage).
- [ ] Desktop entry (`Arova.desktop`) and app icon appear in application launcher.
- [ ] Launches cleanly from application menu without a terminal window.
- [ ] Splash screen displays while background daemon (`arovad`) auto-spawns.
- [ ] Zero system Python/Node dependencies required by the end user.

### 2. Onboarding & Runtime Verification
- [ ] Setup wizard saves chosen provider and API key / host.
- [ ] Retains configuration cleanly across full app restart.
- [ ] "Continue" card appears with accurate context on second launch.
- [ ] Health dashboard reports green (`Test All Providers` probes live status).

### 3. Ugly Cases & Edge Case Resilience
- [ ] **Daemon Kill (`killall arovad`)**: UI shows reconnecting, auto-respawns daemon, session resumes.
- [ ] **Offline (`Wi-Fi Disconnected`)**: App boots cleanly, local memory/Ollama works without errors.
- [ ] **Wrong API Key**: Explains `401 / Invalid Key` clearly rather than raw exception trace.
- [ ] **Ollama Offline**: Reports `Couldn't connect to Ollama` gracefully instead of unknown crash.
- [ ] **Config Wipe (`rm -rf ~/.config/arova`)**: Onboarding restarts cleanly from scratch.
- [ ] **Runtime Wipe (`rm -rf ~/.arova`)**: Daemon reconstructs memory/snapshots cleanly on next boot.
- [ ] **Upgrade Survival**: Memory and replay history survive package upgrade.

### 4. VM Progression Schedule (Before Friend #1)
1. [ ] **Arch Linux Machine** (Daily Driver native validation)
2. [ ] **Ubuntu 24.04 Clean VM** (`Arova.deb` package installation check)
3. [ ] **Fedora Clean VM** (`Arova.rpm` package check)
4. [ ] **Friend #1 Physical Machine** (First external silent observation)

---

## 📊 Daily Dogfooding Log

### Template Entry
```markdown
### Date: YYYY-MM-DD (User / Persona)
- **Hours used**: 0.0 hours
- **Resume Success Rate**:
  - Resumes requested: 0
  - Opened suggested card?: 0
  - Stayed active >60 seconds?: 0
  - Zero manual searches needed?: 0
  - Marked helpful (😊 Perfect): 0
- **Wrong / inaccurate cards**: 0
- **Replay feedback bundles submitted**: 0 (`arova_feedback_*.zip`)
- **Annoyances & frictions**:
  - None
- **Would keep installed today?**: Yes / No
```

---

### Date: 2026-07-19 (Internal Engineering Dogfooding — Day 1 Setup)
- **Hours used**: 4.5 hours (Core evaluation & scenario verification suite)
- **Resumes generated**: 7 (across developer, finance, research, and regression scenarios)
- **Wrong / inaccurate cards**: 0 (Exact Cognitive Recovery: 18/18 facts recovered)
- **Manual searches required**: 0
- **Replay feedback bundles submitted**: 1 (`/tmp/arova_feedback_test.zip` verified)
- **Annoyances & frictions**:
  - Provider onboarding previously limited to Groq/OpenAI. Resolved by registering 6 core pluggable providers (`Ollama`, `OpenAI`, `Groq`, `Anthropic`, `Gemini`, `OpenRouter`).
- **Would keep installed today?**: **Yes**
