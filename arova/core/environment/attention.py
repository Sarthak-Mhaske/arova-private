import time
from dataclasses import dataclass
from collections import deque
from arova.core.platform.windowing.base import WindowingBackend, FocusedWindowEvent

@dataclass
class AttentionState:
    focus_depth: float
    interruption_rate: float
    cognitive_momentum: float
    probable_mode: str # e.g. "deep_work", "fragmented", "idle"

class AttentionGraphEngine:
    """
    Analyzes temporal focus, interruption frequency, and cognitive flow.
    Emits AttentionState to drive emotional coherence in the UI.
    """
    def __init__(self, window_backend: WindowingBackend, event_bus=None):
        self.window_backend = window_backend
        self.event_bus = event_bus
        self._focus_history = deque(maxlen=50) # Keep last 50 focus events (timestamp, window_id)
        self._last_emit_time = 0.0
        self._last_mode = None
        
        self._listeners = []
        self.window_backend.add_listener(self._on_platform_event)
        
    def add_listener(self, callback):
        self._listeners.append(callback)
        
    async def _emit_attention(self, state):
        for listener in self._listeners:
            try:
                await listener(state)
            except Exception:
                pass

    async def _on_platform_event(self, event):
        if isinstance(event, FocusedWindowEvent):
            now = time.time()
            window_id = event.window_data.window_id if event.window_data else "unknown"
            
            # Avoid duplicate rapid events for the same window
            if self._focus_history and self._focus_history[-1][1] == window_id:
                if now - self._focus_history[-1][0] < 0.5:
                    return
                    
            self._focus_history.append((now, window_id))
            
            # Re-evaluate attention state
            await self._reevaluate()

    async def _reevaluate(self):
        now = time.time()
        
        # Calculate interruption rate (context switches per minute over the last 5 mins)
        recent_switches = 0
        for ts, _ in self._focus_history:
            if now - ts <= 300: # 5 minutes window
                recent_switches += 1
                
        interruption_rate = min(1.0, recent_switches / 20.0) # 20 switches in 5 mins is max fragmentation
        
        # Calculate focus depth (time spent in the current window vs recent switches)
        if self._focus_history:
            time_in_current = now - self._focus_history[-1][0]
            focus_depth = min(1.0, time_in_current / 120.0) # 2 minutes without switching = max focus
        else:
            focus_depth = 0.0
            
        # Cognitive Momentum: Sustained directional activity. 
        # For this heuristic, we assume high momentum if interruption rate is low and focus depth is growing steadily.
        # Or if switches happen between a known small cluster of windows (productive switching).
        # We approximate this by checking unique windows in the last 10 switches.
        recent_windows = [wid for ts, wid in list(self._focus_history)[-10:] if now - ts <= 300]
        unique_windows = len(set(recent_windows))
        
        if len(recent_windows) > 2 and unique_windows <= 3:
            # Switching between 2-3 windows frequently = productive context switching (high momentum)
            cognitive_momentum = 0.8
        elif unique_windows > 3:
            # Switching across many unique windows = attention decay (low momentum)
            cognitive_momentum = max(0.0, 1.0 - (unique_windows / 10.0))
        else:
            # Single window focus = momentum tied to focus depth
            cognitive_momentum = 0.5 + (focus_depth * 0.5)
            
        # Determine probable mode
        if focus_depth > 0.7 and cognitive_momentum > 0.7:
            mode = "deep_work"
        elif interruption_rate > 0.6 and cognitive_momentum < 0.4:
            mode = "fragmented"
        elif focus_depth < 0.1 and interruption_rate < 0.1:
            mode = "idle"
        else:
            mode = "active"
            
        # Emit timeline event if mode changed
        if mode != self._last_mode and self.event_bus:
            from arova.core.timeline.events import CATEGORY_STATE_TRANSITION
            self.event_bus.emit("timeline", "create", {
                "category": CATEGORY_STATE_TRANSITION,
                "title": f"Attention Shift: {mode.replace('_', ' ').title()}",
                "description": f"User attention transitioned to {mode.replace('_', ' ')}.",
                "source": "attention_engine",
                "importance": 0.6,
                "metadata": {
                    "focus_depth": focus_depth,
                    "interruption_rate": interruption_rate,
                    "cognitive_momentum": cognitive_momentum,
                    "previous_mode": self._last_mode
                }
            })
            self._last_mode = mode
            
        from arova.core.environment.events import EnvironmentalEvent
        event = EnvironmentalEvent(
            source="attention_engine",
            semantic_type="ATTENTION_STATE_CHANGED",
            confidence=1.0,
            payload={
                "focus_depth": focus_depth,
                "interruption_rate": interruption_rate,
                "cognitive_momentum": cognitive_momentum,
                "probable_mode": mode
            }
        )
        
        await self._emit_attention(event)
