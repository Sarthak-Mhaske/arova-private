import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
from datetime import datetime

class TimelineView(Gtk.Box):
    """
    Live Cognitive Timeline.
    Visualizes intent classification, routing decisions, memory retrievals,
    policy interceptions, and execution graphs in a chronological stream.
    """
    def __init__(self, scheduler):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.scheduler = scheduler
        
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_spacing(8)
        
        lbl = Gtk.Label(label="Live Cognitive Timeline")
        lbl.add_css_class("title-1")
        lbl.set_halign(Gtk.Align.START)
        self.append(lbl)
        
        # Scrolled window for log
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_vexpand(True)
        self.scroll.set_hexpand(True)
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scroll.set_child(self.list_box)
        self.append(self.scroll)
        
        # Subscribe to cognition and environment events
        self.scheduler.bind("COGNITION_STATE_CHANGED", self._on_event)
        self.scheduler.bind("ATTENTION_STATE_CHANGED", self._on_event)
        self.scheduler.bind("AMBIENT_INTENT_DETECTED", self._on_event)
        
    def _on_event(self, event: dict):
        event_type = event.get("event_type", "UNKNOWN")
        payload = event.get("payload", {})
        
        time_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row.set_margin_top(8)
        row.set_margin_bottom(8)
        
        header = Gtk.Label(label=f"[{time_str}] {event_type}")
        header.set_halign(Gtk.Align.START)
        header.add_css_class("caption-heading")
        row.append(header)
        
        # Format payload
        detail_text = str(payload)
        if event_type == "COGNITION_STATE_CHANGED":
            detail_text = f"State: {payload.get('state')} | {payload.get('details', '')}"
        elif event_type == "AMBIENT_INTENT_DETECTED":
            detail_text = f"Intent: {payload.get('intent')}"
            
        details = Gtk.Label(label=detail_text)
        details.set_halign(Gtk.Align.START)
        details.set_wrap(True)
        row.append(details)
        
        self.list_box.append(row)
        
        # Auto-scroll to bottom
        adj = self.scroll.get_vadjustment()
        GLib.idle_add(lambda: adj.set_value(adj.get_upper() - adj.get_page_size()))
