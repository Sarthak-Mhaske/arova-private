import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SessionRecorder:
    """
    Records objective OS signals (window focus, file edits, domains visited)
    and packages them into deterministic JSON Replay Files.
    Allows beta users and developers to capture real workdays and replay them
    through Arova's cognitive substrate without requiring raw code reproduction.
    """
    def __init__(self, event_bus=None):
        self.event_bus = event_bus
        self.recording = False
        self.session_id: Optional[str] = None
        self.events: List[Dict[str, Any]] = []
        self.start_time: float = 0.0

        if self.event_bus:
            self.event_bus.subscribe("context", "fragment_reported", self._on_fragment_reported)

    def start_recording(self, session_name: str = "Live Workday Session"):
        self.recording = True
        self.session_id = f"session_{int(time.time())}"
        self.events = []
        self.start_time = time.time()
        self.satisfaction: Optional[Dict[str, Any]] = None
        logger.info("SessionRecorder: Started recording session '%s' (%s)", session_name, self.session_id)

    def stop_recording(self) -> List[Dict[str, Any]]:
        self.recording = False
        logger.info("SessionRecorder: Stopped recording session '%s'. Captured %d events.", self.session_id, len(self.events))
        return self.events

    def record_satisfaction(self, rating: str, reason: Optional[str] = None):
        """
        Records explicit human ground-truth feedback at the end of a session/resume card.
        Ratings: 'PERFECT' (😊 Perfect), 'OKAY' (😐 Okay), or 'WRONG' (☹️ Wrong).
        If WRONG, captures exact reason (e.g. 'wrong_blocker', 'hallucinated_file').
        """
        self.satisfaction = {
            "rating": rating,
            "reason": reason or "N/A",
            "rated_at": datetime.now().isoformat()
        }
        logger.info("SessionRecorder: Recorded human satisfaction ground truth: %s (Reason: %s)", rating, reason)

    def record_event(self, app_name: str, window_title: str, content_snippet: str = "", duration_s: float = 5.0, tags: Optional[List[str]] = None):
        if not self.recording:
            return
        elapsed = time.time() - self.start_time
        timestamp_str = datetime.fromtimestamp(time.time()).strftime("%H:%M:%S")
        
        event_entry = {
            "timestamp": timestamp_str,
            "elapsed_seconds": round(elapsed, 1),
            "app_name": app_name,
            "window_title": window_title,
            "content_snippet": content_snippet,
            "duration_s": duration_s,
            "tags": tags or []
        }
        self.events.append(event_entry)

    def _on_fragment_reported(self, event: Any):
        if not self.recording:
            return
        payload = event.data if hasattr(event, "data") else event
        if not payload:
            return
        
        app_name = payload.get("provider_id", "unknown")
        window_title = payload.get("source_identity", "unknown")
        snippet = payload.get("activity_summary", "")
        self.record_event(app_name=app_name, window_title=window_title, content_snippet=snippet)

    def export_replay_package(self, 
                              filepath: str, 
                              scenario_id: str = "replays/live_workday",
                              name: str = "Recorded Workday Replay",
                              persona: str = "Beta User",
                              expected_keyword: str = "Arova",
                              expected_facts: Optional[List[str]] = None,
                              expected_capability: str = "AROVA_CAPABILITY_RESUME_WORKSPACE") -> str:
        """
        Exports all recorded events and ground-truth satisfaction to a versioned JSON replay file.
        """
        package = {
            "schema_version": "2.0",
            "scenario_id": scenario_id,
            "name": name,
            "persona": persona,
            "recorded_at": datetime.now().isoformat(),
            "satisfaction": self.satisfaction or {"rating": "UNRATED", "reason": "N/A"},
            "events": self.events,
            "expected_outcome": {
                "expected_workspace_keyword": expected_keyword,
                "expected_facts": expected_facts or [],
                "expected_capability": expected_capability,
                "expected_quality": "BALANCED"
            }
        }
        
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(package, f, indent=2)
            
        logger.info("SessionRecorder: Exported %d events (v2.0 schema) to %s", len(self.events), filepath)
        return filepath

    def record_decision(self, decision_text: str, tags: Optional[List[str]] = None):
        """
        Records an explicit architectural or workflow decision made during the session.
        High cognitive value for replay reconstruction.
        """
        self.record_event(
            app_name="arova_cognition",
            window_title=f"Decision: {decision_text[:45]}...",
            content_snippet=decision_text,
            duration_s=15.0,
            tags=(tags or []) + ["decision"]
        )
        logger.info("SessionRecorder: Recorded decision: %s", decision_text)

    def record_question(self, question_text: str, tags: Optional[List[str]] = None):
        """
        Records an open question or unresolved line of inquiry.
        """
        self.record_event(
            app_name="arova_cognition",
            window_title=f"Question: {question_text[:45]}...",
            content_snippet=question_text,
            duration_s=15.0,
            tags=(tags or []) + ["question"]
        )
        logger.info("SessionRecorder: Recorded question: %s", question_text)

    @classmethod
    def load_replay_from_file(cls, filepath: str) -> Dict[str, Any]:
        """
        Loads a JSON replay file for playback in ScenarioRunner.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data

    def export_diagnostic_bundle(self,
                                 zip_filepath: str,
                                 active_workspace: Any = None,
                                 scenario_id: str = "replays/bug_diagnostic") -> str:
        """
        One-click diagnostic bundle generation.
        Packages Replay JSON, Model Registry state, active workspace state, and health check into a single .zip archive.
        """
        import zipfile
        import tempfile
        from arova.core.models.registry import get_model_registry

        os.makedirs(os.path.dirname(os.path.abspath(zip_filepath)), exist_ok=True)
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Export Replay JSON
            replay_json = os.path.join(tmp_dir, "replay_package.json")
            self.export_replay_package(filepath=replay_json, scenario_id=scenario_id, name="Diagnostic Replay")
            
            # 2. Export Model Registry state
            registry_json = os.path.join(tmp_dir, "model_registry.json")
            with open(registry_json, "w", encoding="utf-8") as rf:
                json.dump(get_model_registry().to_dict(), rf, indent=2)

            # 3. Export Workspace State if present
            workspace_json = os.path.join(tmp_dir, "workspace_state.json")
            if active_workspace and hasattr(active_workspace, "to_dict"):
                with open(workspace_json, "w", encoding="utf-8") as wf:
                    json.dump(active_workspace.to_dict(), wf, indent=2)

            # 4. Export Health Diagnostics
            health_json = os.path.join(tmp_dir, "health_check.json")
            with open(health_json, "w", encoding="utf-8") as hf:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "events_captured": len(self.events),
                    "python_version": sys.version,
                    "platform": sys.platform
                }, hf, indent=2)

            # Create Zip archive
            with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zf:
                for filename in os.listdir(tmp_dir):
                    file_path = os.path.join(tmp_dir, filename)
                    zf.write(file_path, arcname=filename)

        logger.info("SessionRecorder: Exported one-click diagnostic bundle to %s", zip_filepath)
        return zip_filepath
