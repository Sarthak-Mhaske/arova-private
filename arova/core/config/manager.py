import os
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "presence_style": "hybrid",
    "privacy": {
        "workspace_awareness": False,
        "memory_enabled": False,
        "crash_recovery": True,
        "ignored_apps": []
    },
    "runtime": {
        "continuity_decay": "standard"
    },
    "preferred_provider": None,
    "allow_fallback": True
}

DEFAULT_PROVIDERS = {
    "groq": {"api_keys": []},
    "openai": {"api_keys": []},
    "anthropic": {"api_keys": []},
    "ollama": {"host": "http://localhost:11434"}
}

class OSConfigManager:
    """
    Manages the user-facing Human Interaction Contract configurations.
    Separates OS-level UI config from provider credentials.
    Replaces the legacy loader.py which dumped everything into config.yml.
    """
    def __init__(self, config_dir: str = "~/.config/arova"):
        self.config_dir = Path(os.path.expanduser(config_dir))
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_path = self.config_dir / "config.json"
        self.providers_path = self.config_dir / "providers.json"
        
        self._ensure_files()
        
    def _ensure_files(self):
        if not self.config_path.exists():
            self.save_config(DEFAULT_CONFIG)
        if not self.providers_path.exists():
            self.save_providers(DEFAULT_PROVIDERS)
            
    def load_config(self) -> Dict[str, Any]:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Merge with defaults to ensure keys exist
            cfg = DEFAULT_CONFIG.copy()
            for k, v in data.items():
                if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
                    cfg[k] = {**cfg[k], **v}
                else:
                    cfg[k] = v
            return cfg
        except Exception as e:
            logger.error(f"Error loading config.json: {e}")
            return DEFAULT_CONFIG.copy()
            
    def load_providers(self) -> Dict[str, Any]:
        try:
            with open(self.providers_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            cfg = DEFAULT_PROVIDERS.copy()
            for k, v in data.items():
                if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
                    cfg[k] = {**cfg[k], **v}
                else:
                    cfg[k] = v
            return cfg
        except Exception as e:
            logger.error(f"Error loading providers.json: {e}")
            return DEFAULT_PROVIDERS.copy()
            
    def save_config(self, config: Dict[str, Any]):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config.json: {e}")
            
    def save_providers(self, providers: Dict[str, Any]):
        try:
            with open(self.providers_path, "w", encoding="utf-8") as f:
                json.dump(providers, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save providers.json: {e}")

# Global instance pattern for ease of use across core services
_instance = None

def get_config_manager() -> OSConfigManager:
    global _instance
    if _instance is None:
        _instance = OSConfigManager()
    return _instance
