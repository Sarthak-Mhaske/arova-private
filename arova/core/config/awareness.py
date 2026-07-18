from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class AwarenessLayer:
    enabled: bool
    allowed_apps: List[str] = field(default_factory=list)
    description: str = ""

@dataclass
class AwarenessPolicy:
    presence: AwarenessLayer = field(default_factory=lambda: AwarenessLayer(
        enabled=True, 
        description="Sees window titles and active focus time. (e.g. VSCode active for 45 mins)"
    ))
    context: AwarenessLayer = field(default_factory=lambda: AwarenessLayer(
        enabled=True, 
        description="Extracts semantic identities like Repo name or domain. (e.g. Repo: arova)"
    ))
    deep_context: AwarenessLayer = field(default_factory=lambda: AwarenessLayer(
        enabled=False, 
        description="Reads visible file text, browser page text, or terminal output."
    ))
    memory_formation: AwarenessLayer = field(default_factory=lambda: AwarenessLayer(
        enabled=True, 
        description="Allows Arova to persist knowledge and preferences across sessions."
    ))
    vision: AwarenessLayer = field(default_factory=lambda: AwarenessLayer(
        enabled=False, 
        description="Analyzes screenshots when requested or context is ambiguous."
    ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "presence": {"enabled": self.presence.enabled, "allowed_apps": self.presence.allowed_apps},
            "context": {"enabled": self.context.enabled, "allowed_apps": self.context.allowed_apps},
            "deep_context": {"enabled": self.deep_context.enabled, "allowed_apps": self.deep_context.allowed_apps},
            "memory_formation": {"enabled": self.memory_formation.enabled, "allowed_apps": self.memory_formation.allowed_apps},
            "vision": {"enabled": self.vision.enabled, "allowed_apps": self.vision.allowed_apps}
        }

class AwarenessManager:
    """Manages the Awareness Policy and evaluates if a source is permitted."""
    def __init__(self):
        self._policy = AwarenessPolicy()
        
    @property
    def policy(self) -> AwarenessPolicy:
        return self._policy
        
    def update_layer(self, layer_name: str, enabled: bool):
        if hasattr(self._policy, layer_name):
            getattr(self._policy, layer_name).enabled = enabled
            
    def get_currently_hidden(self) -> List[str]:
        hidden = []
        if not self._policy.deep_context.enabled:
            hidden.append("Deep Context Disabled")
        if not self._policy.vision.enabled:
            hidden.append("Vision Disabled")
        if not self._policy.memory_formation.enabled:
            hidden.append("Memory Formation Disabled")
        
        # Hardcoded global exclusions for trust
        hidden.extend([
            "Password Managers",
            "Banking Apps",
            "Private Browser Windows"
        ])
        return hidden
