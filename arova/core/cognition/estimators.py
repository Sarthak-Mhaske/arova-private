import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class NeedEstimator:
    """
    Estimates the probability that the user is stuck, confused, or experiencing an error.
    Focuses on negative signals: repeated terminal failures, unhandled exceptions,
    compiler errors, frozen states, and dwell on error traces.
    """
    def estimate(self, telemetry: Dict[str, Any]) -> float:
        score = 0.0
        
        # 1. Terminal / Process Failures
        consecutive_failures = telemetry.get("terminal_consecutive_failures", 0)
        last_exit_code = telemetry.get("terminal_last_exit_code", 0)
        last_output = (telemetry.get("terminal_last_output") or "").lower()
        
        if consecutive_failures > 0 or last_exit_code != 0:
            score += max(0.85, min(0.35 * (consecutive_failures or 1), 0.95))
            
        if any(err_kw in last_output for err_kw in [
            "traceback (most recent call last)", "syntaxerror:", "nameerror:", "importerror:",
            "modulenotfounderror:", "typeerror:", "unboundlocalerror:", "errno 98", "address already in use",
            "error[e0", "failed to compile", "cannot find module", "cannot find name", "merge conflict"
        ]):
            score = max(score, 0.90)

        # 2. Window Title & Active App Error Keywords
        active_app = telemetry.get("active_app", "").lower()
        window_title = telemetry.get("window_title", "").lower()
        idle_seconds = telemetry.get("idle_seconds", 0)
        
        error_keywords = [
            "error", "exception", "failed", "failure", "panic", "conflict",
            "syntaxerror", "traceback", "debugging", "bug", "crash", "errno"
        ]
        if any(kw in window_title for kw in error_keywords):
            score = max(score, 0.82 + min(0.05 * (idle_seconds / 5), 0.15))
            
        dev_apps = [
            "antigravity", "antigravity-ide", "code", "vscode", "cursor",
            "kitty", "alacritty", "terminal", "foot", "wezterm", "ghostty",
            "pycharm", "intellij", "nvim", "vim", "sublime_text"
        ]
        if any(dev in active_app for dev in dev_apps) and idle_seconds > 20:
            score += 0.15
            
        # 3. High CPU / App Not Responding
        if telemetry.get("app_not_responding", False):
            score = max(score, 0.95)
            
        final_score = min(score, 1.0)
        logger.debug(f"NeedEstimator calculated score: {final_score}")
        return final_score


class OpportunityEstimator:
    """
    Estimates how much value Arova could realistically provide in the current context.
    Prioritizes developer workflows (code, terminal, build, debugging) while preventing
    disruptions during passive consumption (YouTube, Netflix).
    """
    def estimate(self, telemetry: Dict[str, Any]) -> float:
        score = 0.0
        active_app = telemetry.get("active_app", "").lower()
        window_title = telemetry.get("window_title", "").lower()
        
        # Low opportunity activities (passive media consumption)
        passive_domains = ["netflix", "twitch", "prime video", "hulu", "disney+"]
        if any(domain in window_title for domain in passive_domains):
            return 0.0
            
        if "youtube" in window_title or "youtu.be" in window_title:
            if any(k in window_title for k in ["tutorial", "how to", "debug", "course", "lecture", "coding", "python", "rust"]):
                score += 0.5
            else:
                return 0.0  # Suppress generic video watching
                
        # High opportunity activities (developer tools, terminals, IDEs)
        dev_apps = [
            "antigravity", "antigravity-ide", "code", "vscode", "cursor",
            "kitty", "alacritty", "terminal", "foot", "wezterm", "ghostty",
            "pycharm", "intellij", "nvim", "vim", "sublime_text", "figma"
        ]
        if any(dev in active_app for dev in dev_apps):
            score += 0.85
            
        # Dev browsers / docs / GitHub / StackOverflow / Localhost
        if any(b in active_app for b in ["brave", "chrome", "firefox", "edge"]):
            if any(site in window_title for site in ["localhost", "127.0.0.1", "github", "stackoverflow", "docs", "documentation", "api", "console"]):
                score += 0.75
            else:
                score += 0.40
            
        final_score = min(score, 1.0)
        logger.debug(f"OpportunityEstimator calculated score: {final_score}")
        return final_score
