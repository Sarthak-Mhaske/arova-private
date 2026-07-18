import time
from typing import Optional
from arova.core.cognition.providers.base import ContextProvider, ContextFragment, ProviderCapability
from arova.core.cognition.provenance import ProvenanceSource
from arova.core.platform.windowing.base import WindowingBackend

class WindowObserverProvider(ContextProvider):
    """
    Observes the user's active window to infer basic activity.
    Replaces the old WorkspaceSemanticAnalyzer.
    """
    capability = ProviderCapability.PRESENCE
    
    def __init__(self, window_backend: WindowingBackend):
        self.backend = window_backend
        self._last_window = None
        self._focus_start_time = time.time()
        
    def get_id(self) -> str:
        return "core.window_observer"
        
    def get_name(self) -> str:
        return "Window Observer"
        
    async def detect(self) -> bool:
        window = await self.backend.get_active_window()
        if window:
            if self._last_window and self._last_window.app_class != window.app_class:
                self._focus_start_time = time.time()
            self._last_window = window
            return True
        return False
        
    async def summarize(self) -> ContextFragment:
        if not self._last_window:
            return None
            
        focus_duration = time.time() - self._focus_start_time
        
        # Simple heuristic mapping for basic summary
        cls_lower = self._last_window.app_class.lower()
        activity = f"Focused on {self._last_window.title}"
        tags = []
        
        if cls_lower in ["code", "vscode", "cursor"]:
            activity = f"Developing in {self._last_window.app_class}"
            tags.append("development")
        elif cls_lower in ["obsidian", "notion"]:
            activity = f"Writing/Synthesizing in {self._last_window.app_class}"
            tags.append("synthesis")
        elif cls_lower in ["firefox", "chrome", "brave"]:
            activity = f"Browsing the web"
            tags.append("exploration")
            
        prov = ProvenanceSource(
            source_type="workspace",
            source_id=self._last_window.app_class,
            confidence=0.9,
            explanation=f"Active window for {int(focus_duration / 60)} minutes"
        )
        
        return ContextFragment(
            provider_id=self.get_id(),
            activity_summary=activity,
            source_identity=self._last_window.title,
            confidence=0.9,
            importance=0.5 if focus_duration < 300 else 0.8,
            expires_at=None,
            tags=tags,
            provenance=[prov],
            metadata={"focus_duration_seconds": focus_duration}
        )
