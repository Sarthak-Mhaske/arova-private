import asyncio
import time
import logging
from typing import Dict, List, Optional
from arova.core.platform.windowing.base import WindowingBackend, WorkspaceEvent, FocusedWindowEvent, RawWindowData
from arova.core.environment.semantics import SemanticProvider, SemanticContext

logger = logging.getLogger(__name__)

class WorkspaceAwarenessEngine:
    """
    Tracks window topology and recurrence, isolating platform noise 
    from the cognition event bus.
    """
    def __init__(self, window_backend: WindowingBackend, semantic_provider: SemanticProvider, event_bus=None):
        self.window_backend = window_backend
        self.semantic_provider = semantic_provider
        self.event_bus = event_bus
        
        self.active_workspace_id: str = ""
        self.active_window: Optional[RawWindowData] = None
        self.workspace_windows: Dict[str, List[RawWindowData]] = {}
        
        self._last_role = None
        self._last_window_app = None
        self._last_window_title = None
        self._last_window_time = 0.0
        
        # We store callbacks to emit purely semantic/intent events upwards
        self._listeners = []
        
        # Register to raw platform events
        self.window_backend.add_listener(self._on_platform_event)

    def add_listener(self, callback):
        self._listeners.append(callback)
        
    async def _emit_semantic(self, event: dict):
        for listener in self._listeners:
            try:
                await listener(event)
            except Exception as e:
                logger.error(f"Semantic listener error: {e}")

    async def _on_platform_event(self, event):
        if isinstance(event, WorkspaceEvent):
            self.active_workspace_id = event.workspace_id
            await self._reevaluate_workspace()
            
        elif isinstance(event, FocusedWindowEvent):
            if event.window_data:
                self.active_window = event.window_data
                self.active_workspace_id = event.window_data.workspace_id
                
                app_name = event.window_data.app_class or "Unknown App"
                window_title = event.window_data.title or ""
                now = time.time()
                
                from arova.core.config.manager import get_config_manager
                cfg = get_config_manager().load_config()
                ignored = cfg.get("privacy", {}).get("ignored_apps", [])
                
                is_new_app = app_name != self._last_window_app
                is_new_title = window_title != self._last_window_title and len(window_title) > 2
                is_time_gap = (now - self._last_window_time) > 120.0
                
                if app_name not in ignored:
                    if (is_new_app or is_new_title or is_time_gap) and self.event_bus:
                        from arova.core.timeline.events import CATEGORY_ENVIRONMENT
                        desc = f"{app_name} became active." if is_new_app else (f"Switched window to '{window_title}'" if is_new_title else f"Resumed activity in {app_name}.")
                        self.event_bus.emit("timeline", "create", {
                            "category": CATEGORY_ENVIRONMENT,
                            "title": f"App Active: {app_name}",
                            "description": desc,
                            "source": "workspace_engine",
                            "importance": 0.2,  # Low importance so it doesn't spam Important view
                            "metadata": {
                                "app_name": app_name,
                                "window_title": window_title
                            }
                        })
                        self._last_window_app = app_name
                        self._last_window_title = window_title
                        self._last_window_time = now
                
                # Update topology
                ws_id = self.active_workspace_id
                if ws_id not in self.workspace_windows:
                    self.workspace_windows[ws_id] = []
                    
                # Ensure window is in workspace list
                existing = [w for w in self.workspace_windows[ws_id] if w.window_id == event.window_data.window_id]
                if not existing:
                    self.workspace_windows[ws_id].append(event.window_data)
                    
                await self._reevaluate_workspace()

    async def _reevaluate_workspace(self):
        windows = self.workspace_windows.get(self.active_workspace_id, [])
        if not windows and self.active_window:
            windows = [self.active_window]
            
        semantic_ctx = await self.semantic_provider.classify(windows)
        
        if semantic_ctx.role != self._last_role and self.event_bus and self._last_role is not None:
            from arova.core.timeline.events import CATEGORY_STATE_TRANSITION
            self.event_bus.emit("timeline", "create", {
                "category": CATEGORY_STATE_TRANSITION,
                "title": f"Room Changed: {self._last_role.title()} -> {semantic_ctx.role.title()}",
                "description": f"Workspace semantics shifted from {self._last_role} to {semantic_ctx.role}.",
                "source": "workspace_engine",
                "importance": 0.7,
                "metadata": {
                    "previous_role": self._last_role,
                    "new_role": semantic_ctx.role
                }
            })
        self._last_role = semantic_ctx.role
        
        from arova.core.environment.events import EnvironmentalEvent
        
        # Prepare the payload, enriching it with probabilistic cognitive modes
        payload = {
            "workspace_id": self.active_workspace_id,
            "role": semantic_ctx.role,
        }
        
        if hasattr(semantic_ctx, 'probabilities'):
            payload["probabilities"] = {
                "implementation": semantic_ctx.probabilities.implementation,
                "synthesis": semantic_ctx.probabilities.synthesis,
                "exploration": semantic_ctx.probabilities.exploration,
                "fragmentation": semantic_ctx.probabilities.fragmentation,
                "planning": semantic_ctx.probabilities.planning,
                "recovery": semantic_ctx.probabilities.recovery,
                "passive": semantic_ctx.probabilities.passive
            }
            payload["mode_velocity"] = semantic_ctx.mode_velocity
            payload["mode_stability"] = semantic_ctx.mode_stability
        
        # Emit the translated semantic event
        await self._emit_semantic(EnvironmentalEvent(
            source="workspace_engine",
            semantic_type="WORKSPACE_SEMANTICS_CHANGED",
            confidence=semantic_ctx.confidence,
            payload=payload
        ))
