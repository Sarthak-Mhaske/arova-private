import logging
from typing import Dict, Any, List, Optional
from arova.core.cognition.ledger import InvestigationLedger, CompletedWork, Evidence
from arova.core.cognition.estimators import NeedEstimator, OpportunityEstimator
from arova.core.cognition.tool_router import DeterministicToolRouter

logger = logging.getLogger(__name__)

class ProactiveInvestigator:
    """
    Coordinates the autonomous proactive loop:
    1. Scores telemetry (Need + Opportunity)
    2. Routes to appropriate tools
    3. Executes the investigation silently
    4. Produces CompletedWork and attaches Evidence
    5. Applies Cooldowns via the Ledger
    """
    def __init__(self, ledger: InvestigationLedger):
        self.ledger = ledger
        self.need_estimator = NeedEstimator()
        self.opportunity_estimator = OpportunityEstimator()
        self.router = DeterministicToolRouter()
        
        self.latency_metrics = {}
        
        # Thresholds
        self.NEED_THRESHOLD = 0.8
        self.OPPORTUNITY_THRESHOLD = 0.6
        
    def _execute_tool(self, tool: str, telemetry: Dict[str, Any]) -> str:
        """Mock execution of a tool for the sake of the proactive investigation."""
        logger.info(f"Executing tool: {tool}")
        if tool == "terminal":
            return "Analyzed terminal output. Found SyntaxError in line 42."
        elif tool == "read_file":
            return "Read file content. Found missing import."
        elif tool == "vision":
            return "Analyzed screen visually. Found a frozen UI modal."
        elif tool == "git":
            return "Analyzed git status. Found merge conflict in main.py."
        return "Executed tool successfully."
        
    def evaluate_and_investigate(self, telemetry: Dict[str, Any]) -> Optional[CompletedWork]:
        import time
        start_time = time.time()
        self.latency_metrics = {}
        
        need_score = self.need_estimator.estimate(telemetry)
        opp_score = self.opportunity_estimator.estimate(telemetry)
        self.latency_metrics["detection"] = time.time() - start_time
        
        if need_score < self.NEED_THRESHOLD or opp_score < self.OPPORTUNITY_THRESHOLD:
            # Correct silence / Missed opportunity logic would go here
            logger.debug("Scores below threshold. No investigation triggered.")
            return None
            
        logger.info(f"Thresholds crossed! Need={need_score}, Opportunity={opp_score}")
        
        route_start = time.time()
        
        # Build evidence trace early for cooldown check
        evidence = Evidence(
            trigger_signal="telemetry_threshold_crossed",
            context_keys=list(telemetry.keys()),
            raw_data=telemetry
        )
        
        if self.ledger.should_cooldown(evidence):
            logger.info("Investigation aborted due to cooldown on this exact evidence.")
            return None
            
        # Route
        tools_to_run = self.router.route(telemetry)
        route_str = " + ".join(tools_to_run)
        
        self.latency_metrics["routing"] = time.time() - route_start
        exec_start = time.time()
        
        # Execute tools and synthesize (mocked here, would normally use LLM for synthesis)
        investigation_results = []
        for tool in tools_to_run:
            res = self._execute_tool(tool, telemetry)
            investigation_results.append(res)
            
        self.latency_metrics["execution"] = time.time() - exec_start
        reasoning_start = time.time()
            
        synthesis = " ".join(investigation_results)
        
        self.latency_metrics["reasoning"] = time.time() - reasoning_start
        ver_start = time.time()
        # Verify logic would go here
        self.latency_metrics["verification"] = time.time() - ver_start
        
        completed_work = CompletedWork(
            title="Proactive Investigation Complete",
            summary=f"Based on telemetry, I ran [{route_str}] and found: {synthesis}",
            evidence=evidence,
            suggested_actions=[{"label": "Apply Fix", "action": "apply_fix"}]
        )
        
        # Append to Ledger
        self.ledger.append_record(
            trigger="telemetry_threshold_crossed",
            need_score=need_score,
            opp_score=opp_score,
            route=route_str,
            evidence=evidence,
            outcome="Verified Fix Prepared"
        )
        
        return completed_work
