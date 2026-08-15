import os
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any

class ExecutionLogger:
    """
    Structured JSONL logging for the orchestration runtime.
    Append-only, streamable, observability-ready.
    """
    def __init__(self, log_dir: str = "~/.cache/arova"):
        self.log_path = Path(os.path.expanduser(log_dir)) / "execution.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log(self, 
            event: str, 
            plan_id: Optional[str] = None, 
            execution_id: Optional[str] = None,
            step_id: Optional[str] = None, 
            status: Optional[str] = None, 
            duration_ms: int = 0,
            message: Optional[str] = None,
            extra: Optional[Dict[str, Any]] = None):
        """
        Write a structured log entry.
        """
        entry = {
            "timestamp": time.time(),
            "thread": threading.current_thread().name,
            "event": event,
            "plan_id": plan_id,
            "execution_id": execution_id,
            "step_id": step_id,
            "status": status,
            "duration_ms": duration_ms
        }
        
        if message:
            entry["message"] = message
        if extra:
            entry["extra"] = extra
            
        # Remove None values for cleaner logs
        entry = {k: v for k, v in entry.items() if v is not None}
        
        log_line = json.dumps(entry) + "\n"
        
        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(log_line)

# Global singleton for core execution logging
execution_logger = ExecutionLogger()
