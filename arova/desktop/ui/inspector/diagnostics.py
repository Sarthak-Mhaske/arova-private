import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

class DiagnosticsView(Gtk.Box):
    """
    Presence Diagnostics.
    Telemetry dashboard for latency, TTFA, and frame timings.
    """
    def __init__(self, scheduler):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.scheduler = scheduler
        
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_spacing(12)
        
        lbl = Gtk.Label(label="Presence Diagnostics")
        lbl.add_css_class("title-1")
        lbl.set_halign(Gtk.Align.START)
        self.append(lbl)
        
        # Grid for metrics
        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(10)
        
        self.ttfa_val = Gtk.Label(label="-- ms")
        self.ttfa_val.add_css_class("title-2")
        grid.attach(Gtk.Label(label="TTFA (Time To First Audio):"), 0, 0, 1, 1)
        grid.attach(self.ttfa_val, 1, 0, 1, 1)
        
        self.ipc_val = Gtk.Label(label="-- ms")
        self.ipc_val.add_css_class("title-2")
        grid.attach(Gtk.Label(label="Avg IPC Latency:"), 0, 1, 1, 1)
        grid.attach(self.ipc_val, 1, 1, 1, 1)
        
        self.fps_val = Gtk.Label(label="60 FPS")
        self.fps_val.add_css_class("title-2")
        grid.attach(Gtk.Label(label="UI Frame Pacing:"), 0, 2, 1, 1)
        grid.attach(self.fps_val, 1, 2, 1, 1)
        
        self.append(grid)
        
        self.scheduler.bind("DIAGNOSTICS_UPDATE", self._on_diagnostics)
        
    def _on_diagnostics(self, event: dict):
        payload = event.get("payload", {})
        
        if "ttfa_ms" in payload:
            self.ttfa_val.set_text(f"{payload['ttfa_ms']:.1f} ms")
        if "ipc_latency_ms" in payload:
            self.ipc_val.set_text(f"{payload['ipc_latency_ms']:.1f} ms")
