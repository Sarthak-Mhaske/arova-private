import time
import logging
from typing import Dict, Any, List, Optional
from arova.core.cognition.ledger import InvestigationLedger, CompletedWork, Evidence
from arova.core.cognition.estimators import NeedEstimator, OpportunityEstimator
from arova.core.cognition.tool_router import DeterministicToolRouter
from arova.core.automation.blocker_resolver import BlockerResolver
from arova.core.automation.schema import CapabilityRequest

logger = logging.getLogger(__name__)

class ProactiveInvestigator:
    """
    Autonomous Proactive "Eyes On" Investigator:
    1. Evaluates ambient telemetry (Need & Opportunity scores).
    2. Enforces quiet deduplication cooldowns via InvestigationLedger.
    3. Silently captures and inspects screens/windows ("getting eyes on").
    4. Diagnoses terminal blockers, tracebacks, port conflicts, and compiler errors.
    5. Surfaces interactive 1-click fix actions and serene summaries to the UI.
    """
    def __init__(self, ledger: InvestigationLedger, dispatcher: Optional[Any] = None, orchestrator: Optional[Any] = None):
        self.ledger = ledger
        self.dispatcher = dispatcher
        self.orchestrator = orchestrator
        self.need_estimator = NeedEstimator()
        self.opportunity_estimator = OpportunityEstimator()
        self.router = DeterministicToolRouter()
        
        self.latency_metrics: Dict[str, float] = {}
        
        # Thresholds for triggering autonomous eyes-on investigation
        self.NEED_THRESHOLD = 0.80
        self.OPPORTUNITY_THRESHOLD = 0.50

    async def _execute_tool_async(self, tool: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a real diagnostic tool asynchronously.
        """
        logger.info(f"ProactiveInvestigator: Executing tool '{tool}'")
        res = {"tool": tool, "output": "", "actions": []}
        
        if tool == "terminal":
            cmd = telemetry.get("terminal_last_command", "")
            out = telemetry.get("terminal_last_output", "")
            blocker = BlockerResolver.analyze_output(cmd, out)
            if blocker:
                res["output"] = f"Terminal Diagnostic: {blocker['summary']}"
                res["actions"] = blocker.get("actions", [])
                res["error_type"] = blocker.get("error_type")
                res["file"] = blocker.get("file")
                res["line"] = blocker.get("line")
            else:
                res["output"] = f"Analyzed terminal output ({len(out)} chars). No fatal compiler blocker matched."
                
        elif tool == "vision":
            if self.dispatcher and "analyze_screen" in getattr(self.dispatcher, "_backends", {}):
                try:
                    active_app = telemetry.get("active_app", "current window")
                    window_title = telemetry.get("window_title", "")
                    query = f"Check {active_app} window for any errors, warnings, stack traces, or blockers"
                    
                    req = CapabilityRequest(
                        capability="analyze_screen",
                        payload={
                            "query": query,
                            "context": f"Active App: {active_app}\nWindow Title: {window_title}\nTerminal Exit: {telemetry.get('terminal_last_exit_code')}\nTerminal Error: {telemetry.get('terminal_last_output', '')[:200]}"
                        }
                    )
                    obs = await self.dispatcher._backends["analyze_screen"].execute(req)
                    if obs.success and obs.output:
                        res["output"] = obs.output
                    else:
                        res["output"] = f"Vision inspection completed for {active_app}."
                except Exception as e:
                    logger.warning(f"ProactiveInvestigator vision capture failed: {e}")
                    res["output"] = f"Vision tool notice: {e}"
            else:
                res["output"] = "Vision inspection unavailable (dispatcher not attached)."

        elif tool == "read_file":
            file_path = telemetry.get("active_file")
            if not file_path and "terminal_last_output" in telemetry:
                import re
                m = re.search(r'File "([^"]+)"', telemetry["terminal_last_output"])
                if m:
                    file_path = m.group(1)
                    
            if file_path:
                try:
                    import os
                    if os.path.exists(file_path):
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                        res["output"] = f"Read {file_path} ({len(lines)} lines)."
                except Exception as e:
                    res["output"] = f"Could not read file {file_path}: {e}"
            else:
                res["output"] = "No target file specified for read_file."

        elif tool == "git":
            try:
                import subprocess
                p = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, timeout=2)
                res["output"] = f"Git status: {p.stdout.strip() or 'Working tree clean.'}"
            except Exception:
                res["output"] = "Git status check skipped."

        return res

    async def evaluate_and_investigate(self, telemetry: Dict[str, Any]) -> Optional[CompletedWork]:
        start_time = time.time()
        self.latency_metrics = {}
        
        need_score = self.need_estimator.estimate(telemetry)
        opp_score = self.opportunity_estimator.estimate(telemetry)
        self.latency_metrics["detection"] = time.time() - start_time
        
        if need_score < self.NEED_THRESHOLD or opp_score < self.OPPORTUNITY_THRESHOLD:
            logger.debug(f"Scores below threshold (Need={need_score:.2f}, Opp={opp_score:.2f}). Skipping investigation.")
            return None
            
        logger.info(f"ProactiveInvestigator: Thresholds crossed! Need={need_score:.2f}, Opp={opp_score:.2f}")
        
        # Build evidence and check cooldown
        evidence = Evidence(
            trigger_signal="telemetry_threshold_crossed",
            context_keys=list(telemetry.keys()),
            raw_data=telemetry
        )
        
        if self.ledger.should_cooldown(evidence):
            logger.info("ProactiveInvestigator: Aborted due to active cooldown on this exact evidence.")
            return None
            
        route_start = time.time()
        tools_to_run = self.router.route(telemetry)
        route_str = " + ".join(tools_to_run)
        self.latency_metrics["routing"] = time.time() - route_start
        
        # Execute tools
        exec_start = time.time()
        tool_results = []
        collected_actions = []
        vision_summary = ""
        terminal_summary = ""
        
        for tool in tools_to_run:
            t_res = await self._execute_tool_async(tool, telemetry)
            tool_results.append(t_res)
            if t_res.get("actions"):
                collected_actions.extend(t_res["actions"])
            if tool == "vision" and t_res.get("output"):
                vision_summary = t_res["output"]
            if tool == "terminal" and t_res.get("output"):
                terminal_summary = t_res["output"]
                
        self.latency_metrics["execution"] = time.time() - exec_start
        
        # Construct lede and summary
        title = "Proactive Diagnostic"
        active_app = telemetry.get("active_app", "").capitalize() or "Application"
        
        # If terminal/blocker found a concrete error
        for r in tool_results:
            if r.get("error_type"):
                title = f"Detected {r['error_type']} in {active_app}"
                break
                
        if not collected_actions:
            # Default action pill to consult Arova for fix
            collected_actions.append({
                "label": f"Fix Issue in {active_app}",
                "primary": True,
                "eventType": "user.message",
                "eventPayload": {"text": f"help me resolve the error in {active_app}", "vocalize": True}
            })

        # Format clean synthesis summary
        if terminal_summary and "Terminal Diagnostic:" in terminal_summary:
            summary = terminal_summary
            if vision_summary and len(vision_summary) < 500:
                summary += f"\n\n**Visual Context**:\n{vision_summary}"
        elif vision_summary:
            summary = vision_summary
        else:
            summary = f"Analyzed {route_str} on {active_app}. Potential blocker detected."

        completed_work = CompletedWork(
            title=title,
            summary=summary,
            evidence=evidence,
            suggested_actions=collected_actions
        )
        
        # Record in ledger to establish cooldown
        self.ledger.append_record(
            trigger="telemetry_threshold_crossed",
            need_score=need_score,
            opp_score=opp_score,
            route=route_str,
            evidence=evidence,
            outcome="Verified Fix Prepared"
        )
        
        return completed_work

