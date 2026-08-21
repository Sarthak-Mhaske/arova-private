import os
import shutil
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

class RiskLevel(Enum):
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"
    NETWORK = "NETWORK"
    MONEY = "MONEY"
    IDENTITY = "IDENTITY"
    SYSTEM = "SYSTEM"

class NodeState(Enum):
    QUEUED = "Queued"
    RUNNING = "Running"
    WAITING = "Waiting"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    SKIPPED = "Skipped"

import uuid

@dataclass
class CapabilityRequest:
    """
    Backend-agnostic request to execute an action on a specific capability/backend.
    """
    capability: str  # Backend target (e.g. "FileBackend", "CommandBackend", "analyze_screen")
    payload: Dict[str, Any] = field(default_factory=dict)  # Action-specific payload
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: str = ""  # Human readable name (e.g. "Modify File")
    expected_observation: str = ""
    success_criteria: str = ""
    confidence: float = 1.0  # 0.0 to 1.0. If < 0.45, requires user approval
    confidence_reason: str = ""
    risk_level: RiskLevel = RiskLevel.READ
    state: NodeState = NodeState.QUEUED
    retry_policy: int = 0
    rollback: str = "none"
    timeout: int = 60  # seconds

@dataclass
class ExecutionGraph:
    """
    A full graph of capabilities requested to achieve a deep planning goal.
    """
    id: str
    goal: str
    nodes: List[CapabilityRequest]
    max_cost: float = 5.0
    max_time: int = 600  # seconds
    max_tokens: int = 10000
    max_replans: int = 3
    max_steps: int = 20

class CapabilityRegistry:
    """
    Discovers capabilities of the host system dynamically so the planner
    only suggests actions that are actually possible.
    """
    def __init__(self):
        self.capabilities = self._discover()
        
    def _discover(self) -> Dict[str, bool]:
        caps = {
            "terminal": True,  # We assume Python has subprocess
            "filesystem": True, # Python has os/shutil
            "browser": False,
            "vscode": False,
            "git": False,
            "docker": False,
            "open_app": True,
            "list_open_apps": True,
            "focus_window": True,
            "close_window": True,
            "analyze_screen": True,
            "media_control": True if shutil.which("playerctl") else False,
            "search_web": True,
            "set_volume": True if shutil.which("wpctl") or shutil.which("pactl") else False
        }
        
        # Check for Git
        if shutil.which("git"):
            caps["git"] = True
            
        # Check for Docker
        if shutil.which("docker"):
            caps["docker"] = True
            
        # Check for VSCode
        if shutil.which("code") or shutil.which("code-insiders"):
            caps["vscode"] = True
            
        # Check for Browser (very basic check)
        if shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("firefox") or shutil.which("safari"):
            caps["browser"] = True
            
        return caps
        
    def get_capabilities(self) -> Dict[str, bool]:
        return self.capabilities
