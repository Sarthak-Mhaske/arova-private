import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib
import logging

try:
    gi.require_version('Gtk4LayerShell', '1.0')
    from gi.repository import Gtk4LayerShell
    HAS_LAYER_SHELL = True
except (ValueError, ImportError):
    HAS_LAYER_SHELL = False

class NarrativeFeed:
    """
    Transient execution narrative surface.
    Displays semantic cognition steps (e.g. "Recalling workspace setup")
    and live partial transcripts.
    """
    def __init__(self, application: Gtk.Application, viewmodel):
        self.viewmodel = viewmodel
        
        self.win = Gtk.ApplicationWindow(application=application)
        self.win.set_title("Arova Narrative")
        self.win.set_decorated(False)
        self.win.set_resizable(False)
        
        if HAS_LAYER_SHELL:
            Gtk4LayerShell.init_for_window(self.win)
            Gtk4LayerShell.set_layer(self.win, Gtk4LayerShell.Layer.OVERLAY)
            # Anchor to bottom-left, slightly above the edge
            Gtk4LayerShell.set_anchor(self.win, Gtk4LayerShell.Edge.BOTTOM, True)
            Gtk4LayerShell.set_anchor(self.win, Gtk4LayerShell.Edge.LEFT, True)
            Gtk4LayerShell.set_margin(self.win, Gtk4LayerShell.Edge.BOTTOM, 40)
            Gtk4LayerShell.set_margin(self.win, Gtk4LayerShell.Edge.LEFT, 40)
        else:
            self.win.set_default_size(400, 150)
            
        self._build_ui()
        self.win.present()
        
        self.viewmodel.scheduler.bind("COGNITION_STATE_CHANGED", self._on_cognition_state)
        self.viewmodel.scheduler.bind("TRANSCRIPT_PARTIAL", self._on_transcript)
        self.viewmodel.scheduler.bind("TRANSCRIPT_FINAL", self._on_transcript_final)
        self.viewmodel.scheduler.bind("AMBIENT_INTENT_DETECTED", self._on_ambient_intent)
        self.viewmodel.scheduler.bind("COGNITIVE_STREAM_STATE", self._on_cognitive_stream)
        
        # Clear timer ID
        self._clear_timer = 0
        
    def _build_ui(self):
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.main_box.set_margin_top(12)
        self.main_box.set_margin_bottom(12)
        self.main_box.set_margin_start(16)
        self.main_box.set_margin_end(16)
        
        # Transcript label (what the user is saying right now)
        self.transcript_label = Gtk.Label(label="")
        self.transcript_label.set_halign(Gtk.Align.START)
        self.transcript_label.set_wrap(True)
        self.transcript_label.set_opacity(0.7) # Slightly faded
        self.main_box.append(self.transcript_label)
        
        # Stream label (Cognitive Surface States)
        self.stream_label = Gtk.Label(label="")
        self.stream_label.set_halign(Gtk.Align.START)
        self.stream_label.set_wrap(True)
        self.stream_label.set_opacity(0.8)
        self.main_box.append(self.stream_label)
        
        # Narrative label (what Arova is thinking/doing)
        self.narrative_label = Gtk.Label(label="Idle")
        self.narrative_label.set_halign(Gtk.Align.START)
        self.narrative_label.set_wrap(True)
        self.narrative_label.add_css_class("title-3")
        self.main_box.append(self.narrative_label)
        
        self.win.set_child(self.main_box)
        
        # Apply Glassmorphism CSS
        css = b'''
        window {
            background-color: rgba(15, 15, 20, 0.6);
            border-radius: 12px;
        }
        label {
            color: rgba(255, 255, 255, 0.9);
            font-family: "Inter", "Roboto", sans-serif;
        }
        '''
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        
    def _on_cognition_state(self, event: dict):
        payload = event.get("payload", {})
        # Map raw internal states to semantic UI narratives
        raw_state = payload.get("state", "idle")
        
        narrative_map = {
            "idle": "Standing by",
            "listening": "Listening...",
            "synthesizing": "Recalling ambient context",
            "planning": "Preparing execution plan",
            "executing": "Executing capabilities",
            "reflecting": "Reviewing outcome"
        }
        
        # We can also use 'details' from payload for rich descriptions
        # e.g., "Reviewing memory: Morning setup"
        semantic_text = narrative_map.get(raw_state, raw_state.capitalize())
        if raw_state == "idle":
            self.transcript_label.set_text("")
            
        self.narrative_label.set_text(semantic_text)
        self._reset_fade_timer()
        
    def _on_transcript(self, event: dict):
        text = event.get("payload", {}).get("text", "")
        if text:
            self.transcript_label.set_text(f'"{text}..."')
        self._reset_fade_timer()
        
    def _on_transcript_final(self, event: dict):
        text = event.get("payload", {}).get("transcript", "")
        if text:
            self.transcript_label.set_text(f'"{text}"')
        self._reset_fade_timer()
        
    def _on_ambient_intent(self, event: dict):
        payload = event
        if "payload" in event:
            payload = event["payload"]
        
        intent = payload.get("intent", "")
        if intent:
            self.narrative_label.set_text(intent)
            self._reset_fade_timer()

    def _on_cognitive_stream(self, event: dict):
        payload = event.get("payload", event)
        text = payload.get("text", "")
        if text:
            self.stream_label.set_text(text)
        self._reset_fade_timer()

    def _reset_fade_timer(self):
        if self._clear_timer > 0:
            GLib.source_remove(self._clear_timer)
            
        self.win.set_opacity(1.0)
        
        def _fade_out():
            # Fade out smoothly over time in a real implementation
            self.win.set_opacity(0.2)
            self._clear_timer = 0
            return False
            
        # Fade out after 5 seconds of inactivity
        self._clear_timer = GLib.timeout_add(5000, _fade_out)
