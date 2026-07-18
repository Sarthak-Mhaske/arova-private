import os
from enum import Enum
from typing import Any, Dict

from arova.core.memory.storage import MemoryEntry

class StorageRoute(Enum):
    AUTO_SAVE = "auto_save"
    REVIEW_QUEUE = "review_queue"
    CONSENT_REQUIRED = "consent_required"

class MemoryPolicyEngine:
    def __init__(self, config_manager: Any):
        self.config_manager = config_manager
        
    def route(self, memory: MemoryEntry) -> StorageRoute:
        if memory.sensitivity_tier == 1:
            return StorageRoute.AUTO_SAVE
            
        if memory.sensitivity_tier == 3:
            return StorageRoute.CONSENT_REQUIRED
            
        # Tier 2 - Check user preferences
        if self.config_manager:
            config = self.config_manager.load_config()
        else:
            config = {}
            
        memory_policy = config.get("memory_policy", {})
        
        # Check category specific policy first
        cat_policy = memory_policy.get("categories", {}).get(memory.category)
        if cat_policy == "auto_save": return StorageRoute.AUTO_SAVE
        if cat_policy == "review_queue": return StorageRoute.REVIEW_QUEUE
        if cat_policy == "ask": return StorageRoute.CONSENT_REQUIRED
            
        # Fallback to global tier2 policy
        tier2_mode = memory_policy.get("tier2_mode", "review_queue")
        
        if tier2_mode == "auto_save":
            return StorageRoute.AUTO_SAVE
        elif tier2_mode == "ask":
            return StorageRoute.CONSENT_REQUIRED
        else:
            return StorageRoute.REVIEW_QUEUE

    def is_first_tier2(self) -> bool:
        """Check if a Tier 2 memory policy has ever been explicitly set."""
        if not self.config_manager:
            return False
            
        config = self.config_manager.load_config()
        memory_policy = config.get("memory_policy", {})
        # If tier2_mode is explicitly set, we've already done the first-time flow
        return "tier2_mode" not in memory_policy

    def set_tier2_mode(self, mode: str):
        if not self.config_manager: return
        config = self.config_manager.load_config()
        if "memory_policy" not in config:
            config["memory_policy"] = {}
        config["memory_policy"]["tier2_mode"] = mode
        self.config_manager.save_config(config)
