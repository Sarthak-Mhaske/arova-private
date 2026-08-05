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

def get_live_temporal_context_prompt(last_active_timestamp: float | None = None) -> str:
    """
    Generates a live wall-clock date, time, timezone, and user absence gap prompt block.
    Injected directly into LLM prompts so Arova always has exact real-world time awareness.
    """
    import datetime
    now = datetime.datetime.now()
    now_str = now.strftime("%A, %B %d, %Y at %I:%M %p")
    tz_str = time.tzname[0] if time.tzname else "Local Time"
    
    absence_lines = []
    if last_active_timestamp and last_active_timestamp > 0:
        elapsed_seconds = time.time() - last_active_timestamp
        if elapsed_seconds >= 60:
            hours = int(elapsed_seconds // 3600)
            minutes = int((elapsed_seconds % 3600) // 60)
            last_dt = datetime.datetime.fromtimestamp(last_active_timestamp)
            if hours > 0:
                absence_lines.append(f"- User Absence Gap: User was away for ~{hours}h {minutes}m (Last active: {last_dt.strftime('%A %I:%M %p')})")
            else:
                absence_lines.append(f"- User Absence Gap: User was away for ~{minutes} minutes")

    absence_block = ("\n" + "\n".join(absence_lines)) if absence_lines else ""

    return (
        f"========================\n"
        f"LIVE TEMPORAL & TIME CONTEXT\n"
        f"========================\n"
        f"- Current Date & Time: {now_str}\n"
        f"- Timezone: {tz_str}"
        f"{absence_block}\n"
        f"IMPORTANT: You ALWAYS have access to real-time information and the exact current date/time stated above. NEVER state 'I don't have access to real-time information'."
    )
