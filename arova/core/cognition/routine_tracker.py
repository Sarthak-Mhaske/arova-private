import os
import json
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class RoutineTracker:
    """
    Predictive Routine & Pattern Engine for Arova.
    Learns daily usage habits (time of day, active projects, preferred editors/terminals)
    to generate pre-flight auto-resume recommendations.
    """
    def __init__(self, store_path: Optional[str] = None):
        if not store_path:
            config_dir = os.path.expanduser("~/.config/arova")
            os.makedirs(config_dir, exist_ok=True)
            store_path = os.path.join(config_dir, "routine_stats.json")
        self.store_path = store_path
        self.stats: Dict[str, Any] = self._load_stats()

    def _load_stats(self) -> Dict[str, Any]:
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.debug(f"RoutineTracker load failed: {e}")
        return {
            "daily_routines": {},
            "frequent_projects": {},
            "frequent_apps": {}
        }

    def record_activity(self, workspace_title: str, repo_paths: List[str], apps: List[str]):
        hour = time.localtime().tm_hour
        hour_slot = f"{hour:02d}:00"

        # Record hourly project affinity
        slot_data = self.stats["daily_routines"].get(hour_slot, {})
        slot_data[workspace_title] = slot_data.get(workspace_title, 0) + 1
        self.stats["daily_routines"][hour_slot] = slot_data

        # Record project frequency
        for p in repo_paths:
            self.stats["frequent_projects"][p] = self.stats["frequent_projects"].get(p, 0) + 1

        # Record app frequency
        for a in apps:
            self.stats["frequent_apps"][a] = self.stats["frequent_apps"].get(a, 0) + 1

        self._save_stats()

    def predict_next_workspace(() -> Optional[Dict[str, Any]]:
        pass

    def get_preflight_recommendation(self) -> Optional[Dict[str, Any]]:
        hour = time.localtime().tm_hour
        hour_slot = f"{hour:02d}:00"

        slot_data = self.stats["daily_routines"].get(hour_slot, {})
        if not slot_data and self.stats["frequent_projects"]:
            # Fallback to top project
            top_proj = max(self.stats["frequent_projects"].items(), key=lambda x: x[1])[0]
            return {
                "recommended_project": top_proj,
                "confidence": 85,
                "reason": f"Frequently used project ({os.path.basename(top_proj)})"
            }
        
        if slot_data:
            top_ws = max(slot_data.items(), key=lambda x: x[1])[0]
            return {
                "recommended_project": top_ws,
                "confidence": 92,
                "reason": f"Regularly active around {hour_slot}"
            }
        return None

    def _save_stats(self):
        try:
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            logger.debug(f"RoutineTracker save failed: {e}")
