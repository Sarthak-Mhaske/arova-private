import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Dict
import logging
import time

class CancellationToken:
    """A token that can be checked by running tasks to gracefully abort."""
    def __init__(self):
        self._cancelled = False
        self._lock = threading.Lock()

    def cancel(self):
        with self._lock:
            self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

class ObservableThreadPool:
    """A ThreadPoolExecutor wrapper that tracks telemetry."""
    def __init__(self, name: str, max_workers: int):
        self.name = name
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=name)
        
        self._lock = threading.Lock()
        self._active_workers = 0
        self._queued_tasks = 0
        self._total_executed = 0
        self._total_failures = 0

    def submit(self, fn: Callable[..., Any], *args, **kwargs):
        with self._lock:
            self._queued_tasks += 1
            
        def wrapper():
            start_time = time.time()
            with self._lock:
                self._queued_tasks -= 1
                self._active_workers += 1
                
            try:
                res = fn(*args, **kwargs)
                return res
            except Exception as e:
                with self._lock:
                    self._total_failures += 1
                logging.error(f"[{self.name}] Task failed: {e}", exc_info=True)
                raise
            finally:
                latency = time.time() - start_time
                with self._lock:
                    self._active_workers -= 1
                    self._total_executed += 1
                    
        return self._executor.submit(wrapper)

    def shutdown(self, wait: bool = True):
        self._executor.shutdown(wait=wait)

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "max_workers": self.max_workers,
                "active_workers": self._active_workers,
                "queued_tasks": self._queued_tasks,
                "total_executed": self._total_executed,
                "total_failures": self._total_failures,
            }

class ThreadManager:
    """Centralized root for all managed thread pools."""
    def __init__(self):
        # State transitions, Orchestration, Light coordination
        self.runtime_pool = ObservableThreadPool("RuntimePool", max_workers=4)
        
        # Tool execution, Plan running (may block for varying times)
        self.execution_pool = ObservableThreadPool("ExecutionPool", max_workers=8)
        
        # HTTP calls, TTS synthesis, STT API, File I/O
        self.io_pool = ObservableThreadPool("IOPool", max_workers=10)
        
        # Wake word, PyAudio streaming (Needs high priority/isolation)
        self.audio_realtime_pool = ObservableThreadPool("AudioRealtimePool", max_workers=2)

    def shutdown(self, wait: bool = True):
        self.audio_realtime_pool.shutdown(wait=wait)
        self.io_pool.shutdown(wait=wait)
        self.execution_pool.shutdown(wait=wait)
        self.runtime_pool.shutdown(wait=wait)
        
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        return {
            "runtime_pool": self.runtime_pool.get_metrics(),
            "execution_pool": self.execution_pool.get_metrics(),
            "io_pool": self.io_pool.get_metrics(),
            "audio_realtime_pool": self.audio_realtime_pool.get_metrics(),
        }
