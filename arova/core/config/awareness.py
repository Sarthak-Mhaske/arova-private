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
            "presence": {"enabled": self.presence.enabled, "allowed_apps": self.presence.allowed_apps, "description": self.presence.description},
            "context": {"enabled": self.context.enabled, "allowed_apps": self.context.allowed_apps, "description": self.context.description},
            "deep_context": {"enabled": self.deep_context.enabled, "allowed_apps": self.deep_context.allowed_apps, "description": self.deep_context.description},
            "memory_formation": {"enabled": self.memory_formation.enabled, "allowed_apps": self.memory_formation.allowed_apps, "description": self.memory_formation.description},
            "vision": {"enabled": self.vision.enabled, "allowed_apps": self.vision.allowed_apps, "description": self.vision.description}
        }

class AwarenessManager:
    """Manages the Awareness Policy and evaluates if a source is permitted."""
    def __init__(self):
        self._policy = AwarenessPolicy()
        self._load_policy()
        
    def _load_policy(self):
        try:
            from arova.core.config.manager import get_config_manager
            cfg = get_config_manager().load_config()
            awareness_cfg = cfg.get("awareness_policy", {})
            for layer in ["presence", "context", "deep_context", "memory_formation", "vision"]:
                if layer in awareness_cfg and isinstance(awareness_cfg[layer], dict):
                    enabled = awareness_cfg[layer].get("enabled")
                    if enabled is not None and hasattr(self._policy, layer):
                        getattr(self._policy, layer).enabled = bool(enabled)
        except Exception as e:
            pass

    def save_policy(self):
        try:
            from arova.core.config.manager import get_config_manager
            cm = get_config_manager()
            cfg = cm.load_config()
            cfg["awareness_policy"] = self._policy.to_dict()
            cm.save_config(cfg)
        except Exception as e:
            pass

    @property
    def policy(self) -> AwarenessPolicy:
        return self._policy
        
    def update_layer(self, layer_name: str, enabled: bool):
        if hasattr(self._policy, layer_name):
            getattr(self._policy, layer_name).enabled = bool(enabled)
            self.save_policy()
            
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
