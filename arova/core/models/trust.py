from enum import Enum
from dataclasses import dataclass
from typing import Set

class TrustZone(Enum):
    """
    Execution authority levels for models.
    """
    LOCAL = "local"     # Embedded or local inference (Ollama). Highest trust.
    CLOUD = "cloud"     # Remote API inference. Lower trust (suggestions only by default).

@dataclass
class TrustPolicy:
    """
    Rules governing what actions a model in a specific zone can take.
    """
    zone: TrustZone
    can_execute_commands: bool
    can_read_clipboard: bool
    can_modify_files: bool
    can_access_network: bool

class FederatedTrustLayer:
    """
    Enforces trust boundaries between cognition layers.
    """
    def __init__(self):
        self.policies = {
            TrustZone.LOCAL: TrustPolicy(
                zone=TrustZone.LOCAL,
                can_execute_commands=True,
                can_read_clipboard=True,
                can_modify_files=True,
                can_access_network=True
            ),
            TrustZone.CLOUD: TrustPolicy(
                zone=TrustZone.CLOUD,
                can_execute_commands=False, # Cloud can only suggest execution
                can_read_clipboard=False,   # Cloud cannot read clipboard (privacy)
                can_modify_files=False,     # Cloud cannot directly modify files
                can_access_network=True
            )
        }
        
    def get_policy(self, zone: TrustZone) -> TrustPolicy:
        return self.policies[zone]
        
    def assert_action_permitted(self, zone: TrustZone, action_type: str) -> bool:
        """
        Validates if a model operating in `zone` is allowed to perform `action_type`.
        """
        policy = self.get_policy(zone)
        if action_type == "execute_command":
            return policy.can_execute_commands
        if action_type == "read_clipboard":
            return policy.can_read_clipboard
        if action_type == "modify_file":
            return policy.can_modify_files
        if action_type == "access_network":
            return policy.can_access_network
            
        return False # Default deny
