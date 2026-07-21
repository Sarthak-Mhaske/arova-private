import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

class AttentionView(Gtk.Box):
    """
    Attention Observatory.
    Plots focus_depth, interruption_rate, and cognitive_momentum over time
    using live readouts and progress bars bound to ATTENTION_STATE_CHANGED events.
    """
    def __init__(self, scheduler):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.scheduler = scheduler
        
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_spacing(12)
        
        lbl = Gtk.Label(label="Attention Observatory")
        lbl.add_css_class("title-1")
        lbl.set_halign(Gtk.Align.START)
        self.append(lbl)
        
        grid = Gtk.Grid()
        grid.set_column_spacing(20)
        grid.set_row_spacing(20)
        
        # Focus Depth
        grid.attach(Gtk.Label(label="Focus Depth:"), 0, 0, 1, 1)
        self.focus_bar = Gtk.ProgressBar()
        grid.attach(self.focus_bar, 1, 0, 1, 1)
        
        # Interruption Rate
        grid.attach(Gtk.Label(label="Interruption Rate:"), 0, 1, 1, 1)
        self.int_bar = Gtk.ProgressBar()
        self.int_bar.add_css_class("error") # Maybe red
        grid.attach(self.int_bar, 1, 1, 1, 1)
        
        # Cognitive Momentum
        grid.attach(Gtk.Label(label="Cognitive Momentum:"), 0, 2, 1, 1)
        self.mom_bar = Gtk.ProgressBar()
        self.mom_bar.add_css_class("success")
        grid.attach(self.mom_bar, 1, 2, 1, 1)
        
        # Probable Mode
        self.mode_val = Gtk.Label(label="Idle")
        self.mode_val.add_css_class("title-2")
        grid.attach(Gtk.Label(label="Probable Mode:"), 0, 3, 1, 1)
        grid.attach(self.mode_val, 1, 3, 1, 1)
        
        self.append(grid)
        
        self.scheduler.bind("ATTENTION_STATE_CHANGED", self._on_attention)
        
    def _on_attention(self, event: dict):
        payload = event
        if "payload" in event:
            payload = event["payload"]
            
        self.focus_bar.set_fraction(payload.get("focus_depth", 0.0))
        self.int_bar.set_fraction(payload.get("interruption_rate", 0.0))
        self.mom_bar.set_fraction(payload.get("cognitive_momentum", 0.0))
        self.mode_val.set_text(payload.get("probable_mode", "unknown"))
