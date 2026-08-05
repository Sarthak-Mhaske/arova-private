import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class NeedEstimator:
    """
    Estimates the probability that the user is stuck, confused, or waiting.
    Focuses on negative signals: repeated failures, frozen states, long dwells on errors.
    """
    def estimate(self, telemetry: Dict[str, Any]) -> float:
        score = 0.0
        
        # 1. Terminal failures
        consecutive_failures = telemetry.get("terminal_consecutive_failures", 0)
        if consecutive_failures > 0:
            score += min(0.3 * consecutive_failures, 0.9)
            
        # 2. Dwell time on error-prone apps (like terminal or IDE with active error)
        active_app = telemetry.get("active_app", "").lower()
        window_title = telemetry.get("window_title", "").lower()
        idle_seconds = telemetry.get("idle_seconds", 0)
        
        # If they are staring at an error or terminal for a long time
        if "error" in window_title or "exception" in window_title:
            score += min(0.1 * (idle_seconds / 10), 0.6)
            
        if active_app in ["code", "terminal", "iterm", "alacritty"] and idle_seconds > 15:
            score += 0.2
            
        # 3. High CPU / App Not Responding
        if telemetry.get("app_not_responding", False):
            score += 0.8
            
        final_score = min(score, 1.0)
        logger.debug(f"NeedEstimator calculated score: {final_score}")
        return final_score


class OpportunityEstimator:
    """
    Estimates how much value Arova could realistically provide in the current context.
    Aims to prevent Arova from interrupting low-value or passive activities (e.g. YouTube).
    """
    def estimate(self, telemetry: Dict[str, Any]) -> float:
        score = 0.0
        active_app = telemetry.get("active_app", "").lower()
        window_title = telemetry.get("window_title", "").lower()
        
        # Low opportunity activities (passive consumption)
        passive_domains = ["youtube", "netflix", "twitch", "reddit", "twitter"]
        if any(domain in window_title for domain in passive_domains):
            # Check intent: are they watching a tutorial?
            if "tutorial" in window_title or "how to" in window_title or "debug" in window_title:
                score += 0.4  # Moderate opportunity
            else:
                return 0.0  # Zero opportunity for general entertainment
                
        # High opportunity activities (creation, debugging, development)
        dev_apps = ["code", "terminal", "iterm", "figma", "pycharm", "intellij"]
        if active_app in dev_apps:
            score += 0.7
            
        # Documentation usually has moderate opportunity (they are reading, maybe struggling)
        if "docs" in window_title or "documentation" in window_title or "stackoverflow" in window_title:
            score += 0.6
            
        final_score = min(score, 1.0)
        logger.debug(f"OpportunityEstimator calculated score: {final_score}")
        return final_score
