import time
from arova.core.events import RuntimeEventBus as EventBus
from arova.core.telemetry.kpi_metrics import KPITelemetryCollector
from arova.core.capture.engine import ActivityCaptureEngine

def test_kpi_resume_success_flow():
    bus = EventBus()
    collector = KPITelemetryCollector(event_bus=bus)
    capture = ActivityCaptureEngine(event_bus=bus)
    
    # 1. User initiates recovery
    bus.emit("environment", "RECOVERY_INITIATED", {
        "workspace_id": "ws_test_kpi",
        "title": "Arova Architecture"
    })
    time.sleep(0.05)
    
    assert "ws_test_kpi" in collector.active_resume_sessions
    
    # 2. Within 60 seconds, user starts coding (`editor_change` event from `vscode`)
    capture.ingest_event(
        event_type="editor_change",
        source_plugin="vscode",
        normalized_payload={"resource_path": "/home/sarthak/arova/runtime.py"}
    )
    time.sleep(0.05)
    
    # Verify North Star KPI record
    assert len(collector.kpi_history) == 1
    record = collector.kpi_history[0]
    assert record["workspace_id"] == "ws_test_kpi"
    assert record["success"] is True
    assert record["elapsed_seconds"] <= 60.0
    
    summary = collector.get_summary_metrics()
    assert summary["total_resumes"] == 1
    assert summary["successful_resumes"] == 1
    assert summary["resume_success_rate"] == 100.0

def test_kpi_resume_failure_when_search_queried():
    bus = EventBus()
    collector = KPITelemetryCollector(event_bus=bus)
    capture = ActivityCaptureEngine(event_bus=bus)
    
    bus.emit("environment", "RECOVERY_INITIATED", {
        "workspace_id": "ws_test_fail",
        "title": "Arova Architecture"
    })
    time.sleep(0.05)
    
    # User queries search before coding
    bus.emit("search", "query", {"query": "SQLite"})
    time.sleep(0.05)
    
    # Then coding starts
    capture.ingest_event(
        event_type="editor_change",
        source_plugin="vscode",
        normalized_payload={"resource_path": "/home/sarthak/arova/runtime.py"}
    )
    time.sleep(0.05)
    
    assert len(collector.kpi_history) == 1
    assert collector.kpi_history[0]["success"] is False
    assert collector.kpi_history[0]["search_queried"] is True

def test_dogfooding_dashboard_summary():
    collector = KPITelemetryCollector()
    summary = collector.get_dogfooding_dashboard_summary()
    assert summary["resume_attempts"] == 0
    assert summary["successful_resumes"] == 0
    assert summary["manual_searches_after_resume"] == 0
    assert summary["manual_file_opens"] == 0
    assert summary["avg_time_to_first_productive_action_sec"] == 0.0
    assert summary["restores_cancelled"] == 0

def test_expanded_dogfooding_metrics_and_taxonomy():
    collector = KPITelemetryCollector()
    
    # 1. Record failure reasons
    collector.record_failure_reason("missed_important_file", details="Forgot redis config")
    collector.record_failure_reason("wrong_workspace_selected")
    
    # 2. Confidence calibration
    collector.record_confidence_calibration(94, "correct")
    collector.record_confidence_calibration(88, "mostly_correct")
    
    # 3. Acceptance rate
    collector.record_acceptance_event("shown")
    collector.record_acceptance_event("shown")
    collector.record_acceptance_event("clicked")
    
    # 4. Search analytics
    collector.record_search_analytics("sqlite migration", result_clicked=True, time_to_click_sec=2.5, needed_second_search=False)
    
    summary = collector.get_dogfooding_dashboard_summary()
    assert summary["failure_reasons"]["missed_file"] == 1
    assert summary["failure_reasons"]["wrong_workspace"] == 1
    assert summary["confidence_calibration"]["correct_count"] == 1
    assert summary["confidence_calibration"]["total_ratings"] == 2
    assert summary["continue_card_shown_count"] == 2
    assert summary["resume_clicked_count"] == 1
    assert summary["resume_acceptance_rate"] == 50.0
    assert summary["search_analytics"]["total_queries"] == 1
    assert summary["search_analytics"]["click_through_rate"] == 100.0

def test_kpi_funnel_and_four_state_restoration():
    bus = EventBus()
    collector = KPITelemetryCollector(event_bus=bus)
    capture = ActivityCaptureEngine(event_bus=bus)
    
    # 1. Extensible failure taxonomy
    collector.record_failure_reason("Resume", "Wrong workspace", "Picked my old branch instead of current one.")
    assert len(collector.failure_records) == 1
    assert collector.failure_records[0]["category"] == "Resume"
    assert collector.failure_records[0]["subcategory"] == "Wrong workspace"
    assert collector.failure_records[0]["comment"] == "Picked my old branch instead of current one."
    
    # 2. Complete recovery funnel steps
    collector.record_funnel_step("session_101", "context_lost", {"reason": "wifi_drop"})
    collector.record_funnel_step("session_101", "continue_card_shown")
    collector.record_funnel_step("session_101", "ctrl_space")
    collector.record_funnel_step("session_101", "search", {"query": "sqlite"})
    collector.record_funnel_step("session_101", "timeline")
    collector.record_funnel_step("session_101", "resume")
    assert len(collector.funnel_history) == 6
    
    # 3. Four-state restoration tracking (prepared -> opened -> focused -> actually_used)
    collector.track_restored_resources(["/home/sarthak/arova/runtime.py", "/home/sarthak/arova/config.py"])
    assert collector.restored_resources_tracked["/home/sarthak/arova/runtime.py"]["state"] == "prepared"
    
    # Emit open event -> state transitions to 'opened'
    capture.ingest_event("file_opened", "vscode", {"resource_path": "/home/sarthak/arova/runtime.py"})
    time.sleep(0.05)
    assert collector.restored_resources_tracked["/home/sarthak/arova/runtime.py"]["state"] == "opened"
    
    # Emit focus event -> state transitions to 'focused'
    capture.ingest_event("editor_focused", "vscode", {"resource_path": "/home/sarthak/arova/runtime.py"})
    time.sleep(0.05)
    assert collector.restored_resources_tracked["/home/sarthak/arova/runtime.py"]["state"] == "focused"
    
    # Emit edit event -> state transitions to 'actually_used'
    capture.ingest_event("editor_change", "vscode", {"resource_path": "/home/sarthak/arova/runtime.py"})
    time.sleep(0.05)
    assert collector.restored_resources_tracked["/home/sarthak/arova/runtime.py"]["state"] == "actually_used"
    
    summary = collector.get_dogfooding_dashboard_summary()
    assert summary["restoration_utilization"]["restoration_prepared_count"] == 2
    assert summary["restoration_utilization"]["restoration_opened_count"] == 1
    assert summary["restoration_utilization"]["restoration_focused_count"] == 1
    assert summary["restoration_utilization"]["restoration_actually_used_count"] == 1

def test_context_recovery_time_saved_and_search_weight_calibration():
    bus = EventBus()
    collector = KPITelemetryCollector(event_bus=bus)
    
    # 1. Record recovery time saved (`Phase 7 Point 7`)
    collector.record_recovery_time_saved("ws_001", "Arova Alpha", saved_seconds=180.0, switches_avoided=4, resources_prepared=5)
    summary = collector.get_dogfooding_dashboard_summary()
    assert summary["context_recovery_time_saved"]["total_records"] == 1
    assert summary["context_recovery_time_saved"]["total_saved_seconds"] == 180.0
    assert summary["context_recovery_time_saved"]["total_saved_minutes"] == 3.0
    
    # 2. Verify search ranking calibration (`Phase 7 Point 2`)
    from arova.core.cognition.search_index import SearchIndex
    idx = SearchIndex()
    assert idx.weights["text_match"] == 0.35
    idx.calibrate_search_weights({"text_match": 0.50, "recency": 0.50, "time_spent": 0.0, "revisit_count": 0.0, "decision_weight": 0.0, "pin": 0.0})
    assert idx.weights["text_match"] == 0.50
    assert idx.weights["recency"] == 0.50



