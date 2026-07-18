import math
import gi
import cairo
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Graphene, Gdk

class PresenceOrb(Gtk.DrawingArea):
    """
    A living cognition nucleus using native GTK4 Cairo rendering.
    Implements fluid physics (breathing, tension), multi-layer diffusion,
    and cinematic glassmorphism.
    """
    def __init__(self, scheduler=None):
        super().__init__()
        self.set_content_width(120)
        self.set_content_height(120)
        self.set_draw_func(self._on_draw)
        
        self.state = "idle"
        
        # Core physics
        self._radius = 30.0
        self._target_radius = 30.0
        self._breathing_phase = 0.0
        self._rotation_phase = 0.0 # Flow turbulence
        
        # Ripple / Pulse physics
        self._ripple_radius = 0.0
        self._ripple_alpha = 0.0
        self._ripple_speed = 5.0
        
        # Colors (R, G, B, A)
        self._color = (0.35, 0.55, 0.95, 0.6)
        self._target_color = (0.35, 0.55, 0.95, 0.6)
        
        # Interpolation stiffness
        self._stiffness = 4.0
        self._target_stiffness = 4.0
        
        self._attention_momentum = 0.5
        
        self._whisper_text = ""
        self._whisper_alpha = 0.0
        self._whisper_y_offset = 0.0
        self._whisper_color = (1.0, 1.0, 1.0, 1.0)
        
        self._atmosphere = "calm"
        
        if scheduler:
            scheduler.bind("COGNITION_STATE_CHANGED", self._on_cognition_state)
            scheduler.bind("ATTENTION_STATE_CHANGED", self._on_attention_state)
            scheduler.bind("PRESENCE_WHISPER", self._on_presence_whisper)
            scheduler.bind("ATMOSPHERE_CHANGED", self._on_atmosphere_changed)
            
        self.add_tick_callback(self._on_tick)

    def _on_attention_state(self, event: dict):
        state_dict = event.get("payload", event)
        self._attention_momentum = state_dict.get("cognitive_momentum", 0.5)

    def _on_cognition_state(self, event: dict):
        payload = event.get("payload", {})
        new_state = payload.get("state", "idle")
        self.transition_to(new_state)

    def _on_presence_whisper(self, event: dict):
        payload = event.get("payload", event)
        self._whisper_text = payload.get("text", "")
        urgency = payload.get("urgency", "ambient")
        
        self._whisper_alpha = 1.0
        self._whisper_y_offset = 15.0 # Start slightly lower and drift up
        
        if urgency == "warning":
            self._whisper_color = (1.0, 0.8, 0.2, 1.0)
            self._target_color = (1.0, 0.8, 0.2, 0.9)
        elif urgency == "critical":
            self._whisper_color = (1.0, 0.3, 0.3, 1.0)
            self._target_color = (1.0, 0.3, 0.3, 0.9)
            self._target_radius = 50.0
            self._trigger_ripple(speed=12.0)
        else:
            self._whisper_color = (1.0, 1.0, 1.0, 0.85)
            
    def _on_atmosphere_changed(self, event: dict):
        payload = event.get("payload", event)
        self._atmosphere = payload.get("atmosphere", "calm")
        
    def _trigger_ripple(self, speed=5.0):
        self._ripple_radius = self._radius
        self._ripple_alpha = 0.8
        self._ripple_speed = speed

    def transition_to(self, new_state: str):
        if self.state == new_state:
            return
            
        self.state = new_state
        
        if self.state == "listening":
            self._target_radius = 42.0
            self._target_color = (0.1, 0.9, 0.7, 0.85) # Cyan-green
            self._target_stiffness = 8.0
            self._trigger_ripple(speed=6.0)
        elif self.state in ["thinking", "synthesizing", "planning"]:
            self._target_radius = 36.0
            self._target_color = (0.6, 0.3, 0.95, 0.85) # Violet-indigo
            self._target_stiffness = 6.0
        elif self.state == "executing":
            self._target_radius = 48.0
            self._target_color = (0.9, 0.65, 0.1, 0.9) # Amber/gold
            self._target_stiffness = 12.0 # Snappy, directed motion
            self._trigger_ripple(speed=8.0)
        elif self.state == "interrupted":
            self._target_radius = 20.0
            self._target_color = (0.8, 0.2, 0.2, 0.5) # Ripple collapse, dim red
            self._target_stiffness = 25.0 # Rapid collapse
            self._trigger_ripple(speed=15.0)
        else: # idle
            self._target_radius = 32.0
            self._target_color = (0.35, 0.55, 0.95, 0.6) # Calm blue-white
            self._target_stiffness = 4.0 # Smooth, slow recovery easing

    def _on_tick(self, widget, frame_clock):
        dt = 0.016 # Assume ~60fps for simple spring math
        
        # Interpolate stiffness
        self._stiffness += (self._target_stiffness - self._stiffness) * 2.0 * dt
        
        # Interpolate radius
        diff = self._target_radius - self._radius
        self._radius += diff * self._stiffness * dt
        
        # Color interpolation
        c_r = self._color[0] + (self._target_color[0] - self._color[0]) * self._stiffness * dt
        c_g = self._color[1] + (self._target_color[1] - self._color[1]) * self._stiffness * dt
        c_b = self._color[2] + (self._target_color[2] - self._color[2]) * self._stiffness * dt
        c_a = self._color[3] + (self._target_color[3] - self._color[3]) * self._stiffness * dt
        self._color = (c_r, c_g, c_b, max(0.0, min(1.0, c_a)))
        
        # Breathing & Rotation Math
        base_speed = 1.0 + (self._attention_momentum * 2.0)
        
        if self._atmosphere == "fatigued":
            base_speed *= 0.3
        elif self._atmosphere == "fragmented":
            base_speed *= 1.8
        elif self._atmosphere == "intense":
            base_speed *= 1.5
            
        if self.state == "idle":
            self._breathing_phase += (1.5 * base_speed) * dt
            self._rotation_phase += 0.5 * dt
        elif self.state == "listening":
            self._breathing_phase += (3.5 * base_speed) * dt
            self._rotation_phase += 1.2 * dt
        elif self.state in ["thinking", "synthesizing", "planning"]:
            self._breathing_phase += (4.0 * base_speed) * dt
            self._rotation_phase += 4.0 * dt # Internal flow turbulence
        elif self.state == "executing":
            self._breathing_phase += (2.0 * base_speed) * dt
            self._rotation_phase += 2.0 * dt
        elif self.state == "interrupted":
            self._breathing_phase += 8.0 * dt # Erratic fluttering
            
        # Ripple physics
        if self._ripple_alpha > 0:
            self._ripple_radius += 25.0 * self._ripple_speed * dt
            self._ripple_alpha -= 1.2 * self._ripple_speed * dt
            if self._ripple_alpha < 0:
                self._ripple_alpha = 0.0
            
        # Whisper drift and decay
        if self._whisper_alpha > 0:
            self._whisper_alpha -= 0.15 * dt # Slow fade out
            self._whisper_y_offset -= 6.0 * dt # Drift up
            if self._whisper_alpha < 0:
                self._whisper_alpha = 0.0
            
        self.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _on_draw(self, area, cr, width, height):
        cx = width / 2.0
        cy = height / 2.0
        
        # Base inertia/tension math
        breath_mod = math.sin(self._breathing_phase) * 3.5
        
        if self.state == "executing":
            breath_mod *= 0.2 # Stiffer radius
        elif self.state == "interrupted":
            breath_mod *= 2.0 # Erratic flutter
            
        current_r = max(2.0, self._radius + breath_mod)
        
        # 1. Ripple pulse (draws behind the orb)
        if self._ripple_alpha > 0:
            cr.arc(cx, cy, self._ripple_radius, 0, 2 * math.pi)
            cr.set_line_width(2.0)
            cr.set_source_rgba(self._color[0], self._color[1], self._color[2], self._ripple_alpha)
            cr.stroke()
        
        # 2. Outer Diffuse Glow (Large, highly transparent)
        cr.arc(cx, cy, current_r * 2.8, 0, 2 * math.pi)
        outer_grad = cairo.RadialGradient(cx, cy, current_r * 0.5, cx, cy, current_r * 2.8)
        outer_grad.add_color_stop_rgba(0, self._color[0], self._color[1], self._color[2], self._color[3] * 0.25)
        outer_grad.add_color_stop_rgba(1, self._color[0], self._color[1], self._color[2], 0.0)
        cr.set_source(outer_grad)
        cr.fill()
        
        # 3. Mid Glass Layer (Tension layer, offset slightly by rotation phase)
        tension_offset_x = math.cos(self._breathing_phase * 1.3 + self._rotation_phase) * 4.0
        tension_offset_y = math.sin(self._breathing_phase * 0.7 - self._rotation_phase) * 4.0
        cr.arc(cx + tension_offset_x, cy + tension_offset_y, current_r * 1.4, 0, 2 * math.pi)
        mid_grad = cairo.RadialGradient(cx, cy, current_r * 0.5, cx, cy, current_r * 1.4)
        mid_grad.add_color_stop_rgba(0, self._color[0] * 1.3, self._color[1] * 1.3, self._color[2] * 1.3, self._color[3] * 0.7)
        mid_grad.add_color_stop_rgba(1, self._color[0], self._color[1], self._color[2], 0.0)
        cr.set_source(mid_grad)
        cr.fill()
        
        # 4. Dense Inner Core (Sharp, bright highlight)
        cr.arc(cx, cy, current_r * 0.85, 0, 2 * math.pi)
        inner_grad = cairo.RadialGradient(cx - current_r*0.25, cy - current_r*0.25, 0, cx, cy, current_r * 0.85)
        
        # Add internal flow turbulence for thinking
        core_brightness = 1.0
        if self.state in ["thinking", "synthesizing", "planning"]:
            core_brightness = 0.85 + (math.sin(self._rotation_phase * 4.0) * 0.15)
            
        inner_grad.add_color_stop_rgba(0, core_brightness, core_brightness, core_brightness, self._color[3] * 1.2)
        inner_grad.add_color_stop_rgba(0.4, self._color[0], self._color[1], self._color[2], self._color[3])
        inner_grad.add_color_stop_rgba(1, self._color[0]*0.4, self._color[1]*0.4, self._color[2]*0.4, self._color[3]*0.9)
        cr.set_source(inner_grad)
        cr.fill()
        
        # Draw Whisper (Wind-like text attachment drifting upward)
        if self._whisper_alpha > 0 and self._whisper_text:
            cr.set_source_rgba(self._whisper_color[0], self._whisper_color[1], self._whisper_color[2], self._whisper_alpha)
            cr.set_font_size(13)
            cr.move_to(cx + current_r + 25, cy + self._whisper_y_offset)
            cr.show_text(self._whisper_text)

# Local manual test block
if __name__ == "__main__":
    app = Gtk.Application()
    def on_activate(app):
        win = Gtk.ApplicationWindow(application=app, title="Orb Preview")
        orb = PresenceOrb()
        orb.set_halign(Gtk.Align.CENTER)
        orb.set_valign(Gtk.Align.CENTER)
        win.set_child(orb)
        win.set_default_size(250, 250)
        
        # Apply dark background
        css = b"window { background-color: #0f1218; }"
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        win.present()
        
        # Sequence through states
        states = ["idle", "listening", "thinking", "executing", "interrupted"]
        idx = 0
        def cycle_state():
            nonlocal idx
            print(f"Transitioning to: {states[idx % len(states)]}")
            orb.transition_to(states[idx % len(states)])
            
            if states[idx % len(states)] == "thinking":
                orb._on_presence_whisper({"text": "Retrieving memories...", "urgency": "ambient"})
            elif states[idx % len(states)] == "interrupted":
                orb._on_presence_whisper({"text": "Interrupted", "urgency": "warning"})
                
            idx += 1
            return True
        GLib.timeout_add(3000, cycle_state)
        
    app.connect("activate", on_activate)
    app.run()
