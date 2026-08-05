import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DeterministicToolRouter:
    """
    Routes an investigation to the correct tool deterministically based on telemetry.
    Avoids expensive LLM calls for tool selection when structured signals are clear.
    """
    
    def route(self, telemetry: Dict[str, Any]) -> List[str]:
        """
        Returns a list of recommended tools (e.g., ['terminal', 'read_file']).
        """
        routes = []
        active_app = telemetry.get("active_app", "").lower()
        window_title = telemetry.get("window_title", "").lower()
        
        # 1. Terminal / Code Failures
        if telemetry.get("terminal_consecutive_failures", 0) > 0:
            logger.info("ToolRouter: Routing to Terminal + File tools due to consecutive terminal failures.")
            return ["terminal", "read_file"]
            
        # 2. Git conflicts or issues
        if "merge conflict" in telemetry.get("terminal_last_output", "").lower() or "git" in active_app:
            logger.info("ToolRouter: Routing to Git + File tools due to git-related signals.")
            return ["git", "read_file"]
            
        # 3. Vision for GUIs
        gui_apps = ["figma", "photoshop", "illustrator", "excel", "powerpoint"]
        if active_app in gui_apps:
            logger.info(f"ToolRouter: Routing to Vision tool due to GUI app focus ({active_app}).")
            return ["vision"]
            
        # 4. Browser / Web Apps without semantic DOM access
        if active_app in ["chrome", "safari", "firefox", "edge"]:
            # If the user is staring at a browser and NeedScore is high, Vision is often the best fallback
            # since we might not have DOM telemetry for every site.
            logger.info("ToolRouter: Routing to Vision tool for browser context.")
            return ["vision"]
            
        # 5. IDE / Editor errors (if no terminal failure)
        if active_app in ["code", "pycharm", "intellij"]:
            if "error" in window_title or "exception" in window_title:
                logger.info("ToolRouter: Routing to Read File tool for IDE error context.")
                return ["read_file", "terminal"]
                
        # Default Fallback
        logger.info("ToolRouter: No deterministic route found. Falling back to Vision + LLM Reasoning.")
        return ["vision", "reasoning"]
