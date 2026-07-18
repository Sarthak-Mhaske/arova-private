import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
import logging

try:
    gi.require_version('Gtk4LayerShell', '1.0')
    from gi.repository import Gtk4LayerShell
    HAS_LAYER_SHELL = True
except (ValueError, ImportError):
    HAS_LAYER_SHELL = False
    logging.warning("Gtk4LayerShell not available. Falling back to standard Gtk.Window.")

class ApprovalOverlay:
    """
    Floating, spatial approval card for capability execution.
    Uses LayerShell to draw directly on the compositor overlay.
    """
    def __init__(self, application: Gtk.Application, viewmodel):
        self.viewmodel = viewmodel
        
        self.win = Gtk.ApplicationWindow(application=application)
        self.win.set_title("Arova Approval")
        self.win.set_decorated(False)
        self.win.set_resizable(False)
        # Transparent background for glassmorphism
        
        if HAS_LAYER_SHELL:
            Gtk4LayerShell.init_for_window(self.win)
            Gtk4LayerShell.set_layer(self.win, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_anchor(self.win, Gtk4LayerShell.Edge.TOP, True)
            Gtk4LayerShell.set_anchor(self.win, Gtk4LayerShell.Edge.RIGHT, True)
            Gtk4LayerShell.set_margin(self.win, Gtk4LayerShell.Edge.TOP, 20)
            Gtk4LayerShell.set_margin(self.win, Gtk4LayerShell.Edge.RIGHT, 20)
        else:
            self.win.set_default_size(300, 200)

        # UI Layout
        self._build_ui()
        self.win.hide()
        
        # Subscribe to execution intercepts
        self.viewmodel.scheduler.bind("CAPABILITY_REQUIRE_CONFIRMATION", self._on_require_confirmation)

    def _build_ui(self):
        # We use a Box as the main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        
        # Style it to look like a floating glass card
        main_box.add_css_class("card")
        
        # Header
        self.header_label = Gtk.Label(label="Arova wants to:")
        self.header_label.set_halign(Gtk.Align.START)
        main_box.append(self.header_label)
        
        # Action Description
        self.action_label = Gtk.Label(label="")
        self.action_label.set_halign(Gtk.Align.START)
        self.action_label.set_wrap(True)
        # A bit of emphasis
        self.action_label.add_css_class("title-4")
        main_box.append(self.action_label)
        
        # Explanation
        self.why_label = Gtk.Label(label="Why: Executing requested automation.")
        self.why_label.set_halign(Gtk.Align.START)
        self.why_label.set_wrap(True)
        main_box.append(self.why_label)
        
        # Risk framing
        self.risk_label = Gtk.Label(label="Risk: Low")
        self.risk_label.set_halign(Gtk.Align.START)
        main_box.append(self.risk_label)
        
        # Approval Memory
        self.memory_check = Gtk.CheckButton(label="Always trust this capability in this context")
        main_box.append(self.memory_check)
        
        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        
        reject_btn = Gtk.Button(label="Reject")
        reject_btn.connect("clicked", self._on_reject)
        
        approve_btn = Gtk.Button(label="Approve")
        approve_btn.add_css_class("suggested-action")
        approve_btn.connect("clicked", self._on_approve)
        
        btn_box.append(reject_btn)
        btn_box.append(approve_btn)
        main_box.append(btn_box)
        
        self.win.set_child(main_box)
        self._current_execution_id = None
        
    def _on_require_confirmation(self, event: dict):
        payload = event.get("payload", {})
        self._current_execution_id = payload.get("execution_id")
        
        action_text = payload.get("description", "Perform unknown action")
        risk_level = payload.get("permission_tier", "DANGEROUS")
        
        self.action_label.set_text(action_text)
        self.risk_label.set_text(f"Risk: {risk_level.capitalize()}")
        self.memory_check.set_active(False)
        
        self.win.present()
        
    def _on_approve(self, btn):
        self.win.hide()
        if self._current_execution_id:
            # Send IPC message back to daemon
            # self.viewmodel.send_message({"event_type": "APPROVAL_GRANTED", ...})
            pass
            
    def _on_reject(self, btn):
        self.win.hide()
        if self._current_execution_id:
            # Send IPC message back to daemon
            pass
