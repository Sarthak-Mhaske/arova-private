import time
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
from typing import List, Callable

class RenderScheduler:
    """
    Manages frame pacing, delta-time calculation, and interpolation.
    Separates the rendering runtime from GTK's implicit loops.
    """
    def __init__(self, target_fps: int = 60):
        self.target_fps = target_fps
        self._target_dt = 1.0 / target_fps
        self._last_frame_time = time.time()
        self._is_running = False
        
        self._updatables: List[Callable[[float], None]] = []
        self._drawables: List[Callable[[], None]] = []
        self._tick_id = 0
        
    def add_updatable(self, callback: Callable[[float], None]):
        """Callback takes delta_time (float) and updates logical state."""
        self._updatables.append(callback)
        
    def add_drawable(self, callback: Callable[[], None]):
        """Callback queues redraws for widgets."""
        self._drawables.append(callback)
        
    def start(self, widget: Gtk.Widget):
        if not self._is_running:
            self._is_running = True
            self._last_frame_time = time.time()
            self._tick_id = widget.add_tick_callback(self._on_tick)
            
    def stop(self, widget: Gtk.Widget):
        if self._is_running:
            self._is_running = False
            if self._tick_id > 0:
                widget.remove_tick_callback(self._tick_id)
                self._tick_id = 0
                
    def _on_tick(self, widget: Gtk.Widget, frame_clock):
        if not self._is_running:
            return GLib.SOURCE_REMOVE
            
        now = time.time()
        dt = now - self._last_frame_time
        
        # Prevent huge jumps if the app was suspended
        if dt > 0.1:
            dt = self._target_dt
            
        self._last_frame_time = now
        
        # 1. Update Physics / Math
        for updatable in self._updatables:
            updatable(dt)
            
        # 2. Issue Redraws
        for drawable in self._drawables:
            drawable()
            
        return GLib.SOURCE_CONTINUE
