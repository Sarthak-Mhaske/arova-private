import time
from typing import Dict

class RuntimeClock:
    """
    Centralized monotonic timing source for the HyprVoice runtime.
    Use this instead of time.time() for all runtime coordination, silence detection, 
    latency tracking, and timeouts to ensure stability against system clock drifts.
    """
    
    _start_time = time.monotonic()
    
    @staticmethod
    def now() -> float:
        """Returns the current monotonic time in seconds."""
        return time.monotonic()
        
    @staticmethod
    def uptime() -> float:
        """Returns the runtime uptime in seconds."""
        return time.monotonic() - RuntimeClock._start_time

class LatencyTracker:
    """Utility for measuring component execution times."""
    
    def __init__(self):
        self._marks: Dict[str, float] = {}
        
    def start(self, label: str):
        self._marks[label] = RuntimeClock.now()
        
    def end(self, label: str) -> float:
        """Returns elapsed time since start(label) in seconds."""
        start_time = self._marks.pop(label, None)
        if start_time is None:
            return 0.0
        return RuntimeClock.now() - start_time
