import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DeterministicToolRouter:
    """
    Routes an investigation to the correct tool deterministically based on telemetry.
    Selects multimodal eyes-on combinations (Vision + Terminal + Code) for full diagnosis.
    """
    
    def route(self, telemetry: Dict[str, Any]) -> List[str]:
        """
        Returns a list of recommended tools (e.g., ['vision', 'terminal', 'read_file']).
        """
        active_app = telemetry.get("active_app", "").lower()
        window_title = telemetry.get("window_title", "").lower()
        last_output = (telemetry.get("terminal_last_output") or "").lower()
        
        # 1. Terminal / Process / Port / Compiler Failures
        if telemetry.get("terminal_consecutive_failures", 0) > 0 or telemetry.get("terminal_last_exit_code", 0) != 0:
            logger.info("ToolRouter: Routing to Vision + Terminal + File tools due to process failure.")
            return ["vision", "terminal", "read_file"]
            
        # 2. Git conflicts
        if "merge conflict" in last_output or "conflict" in window_title:
            logger.info("ToolRouter: Routing to Git + File tools due to git-related signals.")
            return ["git", "read_file", "vision"]
            
        # 3. IDE / Antigravity / Code Editor errors
        if any(ide in active_app for ide in ["antigravity", "code", "vscode", "cursor", "pycharm", "intellij"]):
            if any(err_kw in window_title or err_kw in last_output for err_kw in ["error", "exception", "failed", "panic", "debugging"]):
                logger.info(f"ToolRouter: Routing to Vision + Read File for IDE error context ({active_app}).")
                return ["vision", "read_file", "terminal"]
            return ["vision", "reasoning"]
            
        # 4. Terminal / Shell App focus
        if any(term in active_app for term in ["kitty", "alacritty", "terminal", "foot", "wezterm"]):
            logger.info("ToolRouter: Routing to Terminal + Vision tools for shell context.")
            return ["vision", "terminal"]
            
        # 5. Browser / Web Apps
        if any(b in active_app for b in ["brave", "chrome", "firefox", "edge"]):
            logger.info("ToolRouter: Routing to Vision tool for browser context.")
            return ["vision"]
            
        # Default Fallback
        logger.info("ToolRouter: Falling back to Vision + Reasoning.")
        return ["vision", "reasoning"]
