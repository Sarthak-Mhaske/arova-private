import time
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class KPITelemetryCollector:
    """
    Instrumented KPI tracking (`Phase 6 & P0-5`).
    Tracks our North Star KPI: `Resume Success`:
    `User clicked Resume -> No manual search -> No reopening files -> Started coding within 60 seconds.`
    Also records `Context Recovery Time Saved`, `Time to Productivity`, `Failure Reasons`, `Confidence Calibration`, `Acceptance Rate`, `Search Analytics`, and `Post-Restore Utilization`.
    """
    def __init__(self, event_bus: Optional[Any] = None):
        self.event_bus = event_bus
        self.active_resume_sessions: Dict[str, Dict[str, Any]] = {}  # workspace_id -> session state
        self.kpi_history: List[Dict[str, Any]] = []
        
        # 1. Failure reasons taxonomy (`Extensible: Category, Subcategory, Comment`)
        self.failure_reasons_tally: Dict[str, int] = {
            "wrong_workspace": 0,
            "missed_file": 0,
            "missed_blocker": 0,
            "story_incorrect": 0,
            "search_missed": 0,
            "wrong_environment": 0,
            "too_slow": 0,
            "other": 0
        }
        self.failure_records: List[Dict[str, Any]] = []
        
        # 2. Confidence calibration
        self.confidence_calibration_records: List[Dict[str, Any]] = []
        
        # 3. Resume Acceptance Rate & Recovery Funnel
        self.continue_card_shown_count: int = 0
        self.resume_clicked_count: int = 0
        self.resume_dismissed_count: int = 0
        self.resume_ignored_count: int = 0
        self.funnel_history: List[Dict[str, Any]] = []
        
        # 4. Search analytics
        self.search_analytics_records: List[Dict[str, Any]] = []
        
        # 5. Restoration utilization (`prepared -> opened -> focused -> actually_used`)
        self.restored_resources_tracked: Dict[str, Dict[str, Any]] = {} # resource_path -> details
        self.restoration_edited_count: int = 0
        self.restoration_wasted_count: int = 0
        self.restoration_prepared_count: int = 0
        self.restoration_opened_count: int = 0
        self.restoration_focused_count: int = 0
        self.recovery_saved_records: List[Dict[str, Any]] = []
        
        if self.event_bus:
            self.event_bus.subscribe("environment", "RECOVERY_INITIATED", self._on_recovery_initiated)
            self.event_bus.subscribe("telemetry", "time_to_productivity", self._on_time_to_productivity)
            self.event_bus.subscribe("telemetry", "context_recovery_saved", self._on_recovery_saved)
            self.event_bus.subscribe("search", "query", self._on_search_query)
            self.event_bus.subscribe("capture", "EVENT_INGESTED", self._on_capture_event)

    def record_recovery_time_saved(self, workspace_id: str, title: str, saved_seconds: float, switches_avoided: int = 0, resources_prepared: int = 0):
        """Manually or programmatically record estimated context recovery time saved (`Phase 7 Point 7`)."""
        self.recovery_saved_records.append({
            "workspace_id": workspace_id,
            "title": title,
            "saved_seconds": float(saved_seconds),
            "saved_minutes": round(float(saved_seconds) / 60.0, 1),
            "switches_avoided": switches_avoided,
            "resources_prepared": resources_prepared,
            "timestamp": time.time()
        })

    def _on_recovery_saved(self, payload: Any):
        data = payload.data if hasattr(payload, 'data') else payload
        if not isinstance(data, dict):
            data = data.__dict__ if hasattr(data, '__dict__') else {}
        self.record_recovery_time_saved(
            workspace_id=str(data.get("workspace_id", "")),
            title=str(data.get("title", "Workspace")),
            saved_seconds=float(data.get("saved_seconds", 0.0)),
            switches_avoided=int(data.get("switches_avoided", 0)),
            resources_prepared=int(data.get("resources_prepared", 0))
        )

    def record_failure_reason(self, category_or_reason: str, subcategory_or_details: Optional[str] = None, comment: Optional[str] = None, details: Optional[str] = None):
        """
        Supports both legacy `(reason, details)` and extensible `(category, subcategory, comment)`.
        """
        if comment is not None or (details is None and subcategory_or_details and " " in subcategory_or_details and not any(k in category_or_reason.lower() for k in ["file", "workspace", "slow", "search"])):
            cat = category_or_reason
            subcat = subcategory_or_details or category_or_reason
            comm = comment or details or ""
        else:
            cat = "Resume"
            subcat = category_or_reason
            comm = subcategory_or_details or details or ""

        self.failure_records.append({
            "category": cat,
            "subcategory": subcat,
            "comment": comm,
            "timestamp": time.time()
        })

        key = subcat.lower().replace(" ", "_")
        if "workspace" in key:
            key = "wrong_workspace"
        elif "file" in key:
            key = "missed_file"
        elif "blocker" in key:
            key = "missed_blocker"
        elif "story" in key or "narrative" in key:
            key = "story_incorrect"
        elif "search" in key:
            key = "search_missed"
        elif "environment" in key or "vscode" in key or "terminal" in key:
            key = "wrong_environment"
        elif "slow" in key or "time" in key:
            key = "too_slow"
            
        if key in self.failure_reasons_tally:
            self.failure_reasons_tally[key] += 1
        else:
            self.failure_reasons_tally["other"] += 1
        logger.info(f"KPITelemetryCollector: Recorded failure category='{cat}' subcat='{subcat}' comment='{comm}'")

    def record_funnel_step(self, session_id: str, step: str, details: Optional[Dict[str, Any]] = None):
        """
        Logs exact stages in the user's recovery journey:
        context_lost -> continue_card_shown -> ignored -> ctrl_space -> search -> timeline -> resume -> vscode_restored -> edited_file -> flow
        """
        self.funnel_history.append({
            "session_id": session_id,
            "step": step.lower(),
            "details": details or {},
            "timestamp": time.time()
        })
        logger.info(f"KPITelemetryCollector: Funnel step '{step}' for session '{session_id}'")

    def record_confidence_calibration(self, score: int, rating: str):
        self.confidence_calibration_records.append({
            "score": score,
            "rating": rating.lower(),
            "timestamp": time.time()
        })
        logger.info(f"KPITelemetryCollector: Recorded confidence calibration score={score}% rating={rating}")

    def record_acceptance_event(self, event_type: str):
        et = event_type.lower()
        if et == "shown":
            self.continue_card_shown_count += 1
        elif et == "clicked":
            self.resume_clicked_count += 1
        elif et == "dismissed":
            self.resume_dismissed_count += 1
        elif et == "ignored":
            self.resume_ignored_count += 1
        logger.info(f"KPITelemetryCollector: Recorded acceptance event '{et}'")

    def record_search_analytics(self, query: str, result_clicked: bool, time_to_click_sec: float, needed_second_search: bool = False):
        self.search_analytics_records.append({
            "query": query,
            "result_clicked": result_clicked,
            "time_to_click_sec": time_to_click_sec,
            "needed_second_search": needed_second_search,
            "timestamp": time.time()
        })
        logger.info(f"KPITelemetryCollector: Recorded search analytics query='{query}' clicked={result_clicked} time={time_to_click_sec:.2f}s")

    def track_restored_resources(self, resource_paths: List[str]):
        now = time.time()
        for path in resource_paths:
            self.restored_resources_tracked[path] = {
                "state": "prepared",
                "prepared_at": now,
                "opened_at": None,
                "focused_at": None,
                "used_at": None,
                "edited": False,
                "closed": False
            }
            self.restoration_prepared_count += 1

    def _on_recovery_initiated(self, payload: Any):
        data = payload.data if hasattr(payload, 'data') else payload
        if not isinstance(data, dict):
            data = data.__dict__ if hasattr(data, '__dict__') else {}
        wid = data.get("workspace_id")
        if not wid:
            return
            
        self.record_acceptance_event("clicked")
        self.record_funnel_step(wid, "resume", {"title": data.get("title", "")})
        self.active_resume_sessions[wid] = {
            "workspace_id": wid,
            "title": data.get("title", ""),
            "resumed_at": time.time(),
            "search_queried": False,
            "manual_file_opened": False,
            "coding_started_at": None,
            "resume_success": False
        }
        logger.info(f"KPITelemetryCollector: Initiated tracking for workspace '{wid}'")

    def _on_search_query(self, payload: Any):
        data = payload.data if hasattr(payload, 'data') else payload
        q = data.get("query", "") if isinstance(data, dict) else ""
        self.record_funnel_step("active", "search", {"query": q})
        # If any active session queried search before coding started, mark search_queried = True
        for session in self.active_resume_sessions.values():
            if session["coding_started_at"] is None:
                session["search_queried"] = True
                self.record_failure_reason("Resume", "Search missed", "User queried search right after resume")

    def _on_capture_event(self, payload: Any):
        data = payload.data if hasattr(payload, 'data') else payload
        if not isinstance(data, dict):
            data = data.__dict__ if hasattr(data, '__dict__') else {}
            
        source = data.get("source_plugin", "").lower()
        event_type = data.get("event_type", "").lower()
        normalized = data.get("normalized_payload", {}) if isinstance(data.get("normalized_payload"), dict) else {}
        res_path = normalized.get("resource_path", "")
        
        # Check utilization of restored resources (`prepared -> opened -> focused -> actually_used`)
        if res_path in self.restored_resources_tracked:
            item = self.restored_resources_tracked[res_path]
            is_open_ev = any(k in event_type for k in ["open"])
            is_focus_ev = any(k in event_type for k in ["focus"])
            is_change_ev = any(k in event_type for k in ["change", "content_change", "file_edit"]) or event_type in ["edit", "editor_change", "file_edited"]

            if item["state"] == "prepared" and (is_open_ev or is_focus_ev or is_change_ev):
                item["state"] = "opened"
                item["opened_at"] = time.time()
                self.restoration_opened_count += 1
            if item["state"] == "opened" and (is_focus_ev or is_change_ev):
                item["state"] = "focused"
                item["focused_at"] = time.time()
                self.restoration_focused_count += 1
            if not item["edited"] and is_change_ev:
                item["state"] = "actually_used"
                item["used_at"] = time.time()
                item["edited"] = True
                self.restoration_edited_count += 1
            elif not item["edited"] and not item["closed"] and ("close" in event_type):
                item["closed"] = True
                self.restoration_wasted_count += 1

        # Check if this observation is manual file opening or coding
        is_change_ev = any(k in event_type for k in ["change", "content_change", "file_edit"]) or event_type in ["edit", "editor_change", "file_edited"]
        is_coding = source in ["vscode", "editor", "jetbrains"] or is_change_ev
        
        now = time.time()
        for wid, session in list(self.active_resume_sessions.items()):
            if session["coding_started_at"] is None and is_coding:
                session["coding_started_at"] = now
                elapsed = now - session["resumed_at"]
                self.record_funnel_step(wid, "flow", {"elapsed_sec": round(elapsed, 1)})
                
                # Evaluate North Star KPI: Time to Flow (Time to First Productive Action <= 60s)
                is_success = (elapsed <= 60.0) and not session["search_queried"] and not session["manual_file_opened"]
                session["resume_success"] = is_success
                session["elapsed_to_coding"] = elapsed
                
                if not is_success and elapsed > 60.0:
                    self.record_failure_reason("Resume", "Too slow", f"Elapsed {elapsed:.1f}s to flow")
                
                logger.info(f"KPI Metric [Time to Flow / Resume Success]: {is_success} ({elapsed:.1f}s, search_used={session['search_queried']}) for '{session['title']}'")
                
                metric_record = {
                    "kpi": "resume_success",
                    "workspace_id": wid,
                    "title": session["title"],
                    "success": is_success,
                    "elapsed_seconds": elapsed,
                    "search_queried": session["search_queried"],
                    "timestamp": now
                }
                self.kpi_history.append(metric_record)
                
                if self.event_bus:
                    self.event_bus.emit("telemetry", "kpi_resume_success", metric_record)

    def _on_time_to_productivity(self, payload: Any):
        data = payload.data if hasattr(payload, 'data') else payload
        if not isinstance(data, dict):
            data = data.__dict__ if hasattr(data, '__dict__') else {}
        logger.info(f"KPI Metric [Time to Productivity / Flow]: {data.get('seconds', 0):.2f}s for '{data.get('title')}'")

    def get_summary_metrics(self) -> Dict[str, Any]:
        if not self.kpi_history:
            return {"total_resumes": 0, "resume_success_rate": 0.0, "avg_time_to_productivity": 0.0}
            
        total = len(self.kpi_history)
        successful = sum(1 for r in self.kpi_history if r.get("success", False))
        avg_time = sum(r.get("elapsed_seconds", 0) for r in self.kpi_history) / total
        
        return {
            "total_resumes": total,
            "successful_resumes": successful,
            "resume_success_rate": round((successful / total) * 100.0, 1),
            "avg_time_to_productivity": round(avg_time, 1)
        }

    def get_dogfooding_dashboard_summary(self) -> Dict[str, Any]:
        """
        Returns the exact core and expanded metrics for internal dogfooding (`Phase 7 Dogfooding Freeze`).
        Exclusively returns real telemetry measured from actual usage (zero fabricated/default seeds).
        """
        total_saved_sec = sum(r.get("saved_seconds", 0.0) for r in self.recovery_saved_records)
        total_saved_min = round(total_saved_sec / 60.0, 1)
        avg_saved_sec = round(total_saved_sec / len(self.recovery_saved_records), 1) if self.recovery_saved_records else 0.0
        recovery_saved_summary = {
            "total_records": len(self.recovery_saved_records),
            "total_saved_seconds": round(total_saved_sec, 1),
            "total_saved_minutes": total_saved_min,
            "avg_saved_seconds_per_resume": avg_saved_sec,
            "history": self.recovery_saved_records[-10:]
        }

        if not self.kpi_history and self.continue_card_shown_count == 0:
            return {
                "resume_attempts": 0,
                "successful_resumes": 0,
                "manual_searches_after_resume": 0,
                "manual_file_opens": 0,
                "avg_time_to_first_productive_action_sec": 0.0,
                "restores_cancelled": 0,
                "failure_reasons": self.failure_reasons_tally,
                "failure_records": self.failure_records,
                "confidence_calibration": {
                    "total_ratings": 0,
                    "correct_count": 0,
                    "mostly_correct_count": 0,
                    "wrong_count": 0
                },
                "resume_acceptance_rate": 0.0,
                "continue_card_shown_count": 0,
                "resume_clicked_count": 0,
                "resume_dismissed_count": 0,
                "resume_ignored_count": 0,
                "funnel_history": self.funnel_history,
                "search_analytics": {
                    "total_queries": 0,
                    "click_through_rate": 0.0,
                    "avg_time_to_click_sec": 0.0,
                    "needed_second_search_rate": 0.0
                },
                "restoration_utilization": {
                    "restoration_prepared_count": self.restoration_prepared_count,
                    "restoration_opened_count": self.restoration_opened_count,
                    "restoration_focused_count": self.restoration_focused_count,
                    "restoration_actually_used_count": self.restoration_edited_count,
                    "restoration_edited_count": self.restoration_edited_count,
                    "restoration_wasted_count": self.restoration_wasted_count
                },
                "context_recovery_time_saved": recovery_saved_summary
            }
            
        total = len(self.kpi_history)
        successful = sum(1 for r in self.kpi_history if r.get("success", False))
        manual_searches = sum(1 for r in self.kpi_history if r.get("search_queried", False))
        manual_files = sum(1 for r in self.kpi_history if r.get("manual_file_opened", False))
        avg_time = sum(r.get("elapsed_seconds", 0.0) for r in self.kpi_history) / total if total > 0 else 0.0
        cancelled = sum(1 for r in self.kpi_history if r.get("cancelled", False))

        acc_rate = (self.resume_clicked_count / self.continue_card_shown_count * 100.0) if self.continue_card_shown_count > 0 else 0.0

        cal_total = len(self.confidence_calibration_records)
        cal_correct = sum(1 for c in self.confidence_calibration_records if c["rating"] == "correct")
        cal_mostly = sum(1 for c in self.confidence_calibration_records if c["rating"] == "mostly_correct")
        cal_wrong = sum(1 for c in self.confidence_calibration_records if c["rating"] == "wrong")

        search_total = len(self.search_analytics_records)
        search_clicks = sum(1 for s in self.search_analytics_records if s["result_clicked"])
        search_ctr = (search_clicks / search_total * 100.0) if search_total > 0 else 0.0
        search_avg_time = sum(s["time_to_click_sec"] for s in self.search_analytics_records if s["result_clicked"]) / search_clicks if search_clicks > 0 else 0.0
        search_retry = sum(1 for s in self.search_analytics_records if s["needed_second_search"])
        search_retry_rate = (search_retry / search_total * 100.0) if search_total > 0 else 0.0

        return {
            "resume_attempts": total,
            "successful_resumes": successful,
            "manual_searches_after_resume": manual_searches,
            "manual_file_opens": manual_files,
            "avg_time_to_first_productive_action_sec": round(avg_time, 1),
            "restores_cancelled": cancelled,
            "failure_reasons": self.failure_reasons_tally,
            "failure_records": self.failure_records,
            "confidence_calibration": {
                "total_ratings": cal_total,
                "correct_count": cal_correct,
                "mostly_correct_count": cal_mostly,
                "wrong_count": cal_wrong
            },
            "resume_acceptance_rate": round(acc_rate, 1),
            "continue_card_shown_count": self.continue_card_shown_count,
            "resume_clicked_count": self.resume_clicked_count,
            "resume_dismissed_count": self.resume_dismissed_count,
            "resume_ignored_count": self.resume_ignored_count,
            "funnel_history": self.funnel_history,
            "search_analytics": {
                "total_queries": search_total,
                "click_through_rate": round(search_ctr, 1),
                "avg_time_to_click_sec": round(search_avg_time, 2),
                "needed_second_search_rate": round(search_retry_rate, 1)
            },
            "restoration_utilization": {
                "restoration_prepared_count": self.restoration_prepared_count,
                "restoration_opened_count": self.restoration_opened_count,
                "restoration_focused_count": self.restoration_focused_count,
                "restoration_actually_used_count": self.restoration_edited_count,
                "restoration_edited_count": self.restoration_edited_count,
                "restoration_wasted_count": self.restoration_wasted_count
            },
            "context_recovery_time_saved": recovery_saved_summary
        }
