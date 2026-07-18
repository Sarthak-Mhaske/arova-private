"""
Arova Chat Surface

The primary interaction surface. A unified window containing:
- Left: Narrative/Cognition stream (messages, execution cards)
- Bottom: Floating glass command input
- Right: Workspace awareness sidebar (future)
- Embedded: Presence Orb as emotional anchor

Communicates with the Arova daemon over Unix socket IPC.
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Pango
import logging
import time

from arova.desktop.ui.markdown.renderer import MarkdownTextView
from arova.desktop.ui.orb.presence_orb import PresenceOrb


# ─── Message Model ────────────────────────────────────────────────────────

class MessageRole:
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    COGNITION = "cognition"  # Internal thought stream


class Message:
    def __init__(self, role: str, content: str, timestamp: float = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or time.time()


# ─── Message Bubble Widget ───────────────────────────────────────────────

class MessageBubble(Gtk.Box):
    """
    A single message in the narrative feed.
    Uses MarkdownTextView for assistant responses.
    """
    def __init__(self, message: Message):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.message = message
        
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        
        if message.role == MessageRole.USER:
            self._build_user_bubble()
        elif message.role == MessageRole.ASSISTANT:
            self._build_assistant_bubble()
        elif message.role == MessageRole.COGNITION:
            self._build_cognition_bubble()
        elif message.role == MessageRole.SYSTEM:
            self._build_system_bubble()
    
    def _build_user_bubble(self):
        self.set_halign(Gtk.Align.END)
        
        frame = Gtk.Frame()
        frame.add_css_class("user-bubble")
        
        label = Gtk.Label(label=self.message.content)
        label.set_wrap(True)
        label.set_max_width_chars(60)
        label.set_halign(Gtk.Align.START)
        label.set_margin_top(10)
        label.set_margin_bottom(10)
        label.set_margin_start(14)
        label.set_margin_end(14)
        label.add_css_class("user-text")
        
        frame.set_child(label)
        self.append(frame)
    
    def _build_assistant_bubble(self):
        self.set_halign(Gtk.Align.FILL)
        self.set_margin_end(100) # Prevents taking up the whole screen, acts as max-width
        
        frame = Gtk.Frame()
        frame.add_css_class("assistant-bubble")
        
        md_view = MarkdownTextView()
        md_view.render(self.message.content)
        md_view.set_margin_top(6)
        md_view.set_margin_bottom(6)
        
        frame.set_child(md_view)
        self.append(frame)
        self._md_view = md_view
    
    def _build_cognition_bubble(self):
        self.set_halign(Gtk.Align.START)
        
        label = Gtk.Label(label=self.message.content)
        label.set_wrap(True)
        label.set_halign(Gtk.Align.START)
        label.add_css_class("cognition-text")
        label.set_opacity(0.6)
        self.append(label)
    
    def _build_system_bubble(self):
        self.set_halign(Gtk.Align.CENTER)
        
        label = Gtk.Label(label=self.message.content)
        label.set_wrap(True)
        label.add_css_class("system-text")
        label.set_opacity(0.5)
        self.append(label)
    
    def append_streamed_text(self, text: str):
        """Append text to an assistant bubble during streaming."""
        if hasattr(self, '_md_view'):
            self.message.content += text
            self._md_view.render(self.message.content)


# ─── Chat Surface ────────────────────────────────────────────────────────

class ChatSurface(Gtk.Box):
    """
    The main chat surface widget. Contains the message feed and input.
    Designed to be embedded in the unified main window.
    """
    def __init__(self, scheduler=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.scheduler = scheduler
        self._messages: list[Message] = []
        self._current_stream_bubble: MessageBubble = None
        
        self._build_ui()
        
        if scheduler:
            scheduler.bind("TRANSCRIPT_FINAL", self._on_transcript)
            scheduler.bind("LLM_STREAM_CHUNK", self._on_llm_chunk)
            scheduler.bind("LLM_STREAM_COMPLETE", self._on_llm_complete)
            scheduler.bind("COGNITIVE_STREAM_STATE", self._on_cognition_stream)
    
    def _build_ui(self):
        # ─── Message Feed ─────────────────────────────
        self._scroll = Gtk.ScrolledWindow()
        self._scroll.set_vexpand(True)
        self._scroll.set_hexpand(True)
        self._scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self._feed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._feed_box.set_valign(Gtk.Align.END)  # Messages gravity-bottom
        self._feed_box.set_margin_bottom(16)
        
        self._scroll.set_child(self._feed_box)
        self.append(self._scroll)
        
        # ─── Input Area ───────────────────────────────
        input_frame = Gtk.Frame()
        input_frame.add_css_class("input-surface")
        input_frame.set_margin_start(16)
        input_frame.set_margin_end(16)
        input_frame.set_margin_bottom(16)
        input_frame.set_margin_top(8)
        
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        input_box.set_margin_top(10)
        input_box.set_margin_bottom(10)
        input_box.set_margin_start(14)
        input_box.set_margin_end(14)
        
        self._input_entry = Gtk.Entry()
        self._input_entry.set_hexpand(True)
        self._input_entry.set_placeholder_text("Ask Arova anything...")
        self._input_entry.add_css_class("chat-input")
        self._input_entry.connect("activate", self._on_input_activate)
        
        send_btn = Gtk.Button()
        send_btn.set_icon_name("go-next-symbolic")
        send_btn.add_css_class("send-button")
        send_btn.connect("clicked", self._on_send_clicked)
        
        input_box.append(self._input_entry)
        input_box.append(send_btn)
        input_frame.set_child(input_box)
        
        self.append(input_frame)
    
    def _on_input_activate(self, entry):
        self._send_message()
    
    def _on_send_clicked(self, btn):
        self._send_message()
    
    def _send_message(self):
        text = self._input_entry.get_text().strip()
        if not text:
            return
        
        self._input_entry.set_text("")
        
        # Add user message to feed
        msg = Message(role=MessageRole.USER, content=text)
        self._add_message(msg)
        
        # TODO: Send to daemon over IPC
        # For now, simulate a response
        GLib.timeout_add(500, self._simulate_response, text)
    
    def _simulate_response(self, user_text: str):
        """Placeholder until IPC is wired. Shows streaming simulation."""
        # Add cognition step
        cog = Message(role=MessageRole.COGNITION, content="Evaluating context...")
        self._add_message(cog)
        
        # Simulate streamed assistant response
        response = f"I understand you said: **\"{user_text}\"**\n\nI'm currently running in *preview mode* without the daemon connected. Once connected, I'll:\n\n1. Route your query through the **orchestrator**\n2. Execute any necessary `tools`\n3. Stream the response in real-time\n\n```python\n# Future: IPC integration\nawait daemon.send(user_text)\n```\n\n> This is a static preview of the chat surface."
        
        msg = Message(role=MessageRole.ASSISTANT, content=response)
        self._add_message(msg)
        return False
    
    def _add_message(self, message: Message):
        self._messages.append(message)
        bubble = MessageBubble(message)
        self._feed_box.append(bubble)
        
        # Scroll to bottom
        GLib.idle_add(self._scroll_to_bottom)
    
    def _scroll_to_bottom(self):
        adj = self._scroll.get_vadjustment()
        adj.set_value(adj.get_upper())
        return False
    
    # ─── IPC Event Handlers ───────────────────────────
    
    def _on_transcript(self, event: dict):
        payload = event.get("payload", {})
        text = payload.get("transcript", "")
        if text:
            msg = Message(role=MessageRole.USER, content=text)
            self._add_message(msg)
    
    def _on_llm_chunk(self, event: dict):
        payload = event.get("payload", {})
        chunk = payload.get("text", "")
        if not self._current_stream_bubble:
            msg = Message(role=MessageRole.ASSISTANT, content="")
            self._current_stream_bubble = MessageBubble(msg)
            self._messages.append(msg)
            self._feed_box.append(self._current_stream_bubble)
        self._current_stream_bubble.append_streamed_text(chunk)
        GLib.idle_add(self._scroll_to_bottom)
    
    def _on_llm_complete(self, event: dict):
        self._current_stream_bubble = None
    
    def _on_cognition_stream(self, event: dict):
        payload = event.get("payload", event)
        text = payload.get("text", "")
        if text:
            msg = Message(role=MessageRole.COGNITION, content=text)
            self._add_message(msg)


# ─── Unified Main Window ──────────────────────────────────────────────────

class ArovaMainWindow(Gtk.ApplicationWindow):
    """
    The unified Arova experience window.
    
    Layout:
    ┌──────────────────────────────────────────┐
    │                                          │
    │          Chat / Narrative Feed            │
    │                                          │
    │                                    [Orb] │
    ├──────────────────────────────────────────┤
    │       Floating Glass Input Surface       │
    └──────────────────────────────────────────┘
    """
    def __init__(self, application: Gtk.Application, scheduler=None):
        super().__init__(application=application, title="Arova")
        self.scheduler = scheduler
        self.set_default_size(800, 650)
        
        self._build_ui()
        self._apply_css()
    
    def _build_ui(self):
        # Main overlay — allows the orb to float over the chat
        overlay = Gtk.Overlay()
        self.set_child(overlay)
        
        # Chat surface is the base layer
        self._chat = ChatSurface(scheduler=self.scheduler)
        overlay.set_child(self._chat)
        
        # Presence Orb floats in the bottom-right
        self._orb = PresenceOrb(scheduler=self.scheduler)
        self._orb.set_size_request(100, 100)
        self._orb.set_halign(Gtk.Align.END)
        self._orb.set_valign(Gtk.Align.END)
        self._orb.set_margin_end(24)
        self._orb.set_margin_bottom(90)  # Above input bar
        overlay.add_overlay(self._orb)
    
    def _apply_css(self):
        css = b"""
        /* --- Global -------------------------------- */
        window {
            background-color: #0a0d14;
        }

        /* --- User Bubble --------------------------- */
        .user-bubble {
            background-color: rgba(60, 90, 180, 0.25);
            border-radius: 16px 16px 4px 16px;
            border: 1px solid rgba(100, 140, 255, 0.15);
        }
        .user-text {
            color: rgba(210, 225, 255, 0.92);
            font-family: "Inter", "Roboto", sans-serif;
            font-size: 14px;
        }

        /* --- Assistant Bubble ---------------------- */
        .assistant-bubble {
            background-color: rgba(255, 255, 255, 0.04);
            border-radius: 16px 16px 16px 4px;
            border: 1px solid rgba(255, 255, 255, 0.06);
        }

        /* --- Cognition Stream ---------------------- */
        .cognition-text {
            color: rgba(160, 140, 255, 0.7);
            font-family: "Inter", "Roboto", sans-serif;
            font-size: 12px;
            font-style: italic;
            padding: 4px 16px;
        }

        /* --- System Text --------------------------- */
        .system-text {
            color: rgba(180, 190, 210, 0.5);
            font-family: "Inter", "Roboto", sans-serif;
            font-size: 11px;
        }

        /* --- Input Surface ------------------------- */
        .input-surface {
            background-color: rgba(20, 24, 35, 0.7);
            border-radius: 20px;
            border: 1px solid rgba(100, 140, 255, 0.12);
        }
        .chat-input {
            background: transparent;
            border: none;
            outline: none;
            box-shadow: none;
            color: rgba(220, 230, 250, 0.9);
            font-family: "Inter", "Roboto", sans-serif;
            font-size: 14px;
            caret-color: rgba(120, 160, 255, 0.8);
            min-height: 28px;
        }
        .chat-input:focus {
            outline: none;
            box-shadow: none;
        }

        /* --- Send Button --------------------------- */
        .send-button {
            background-color: rgba(80, 120, 255, 0.3);
            border-radius: 14px;
            border: 1px solid rgba(100, 140, 255, 0.2);
            color: rgba(180, 200, 255, 0.9);
            min-width: 36px;
            min-height: 36px;
            padding: 0;
        }
        .send-button:hover {
            background-color: rgba(80, 120, 255, 0.5);
        }

        /* --- Markdown TextView --------------------- */
        .md-textview {
            background-color: transparent;
        }
        textview text {
            background-color: transparent;
        }

        /* --- ScrolledWindow ------------------------ */
        scrolledwindow undershoot.top, scrolledwindow undershoot.bottom,
        scrolledwindow overshoot.top, scrolledwindow overshoot.bottom {
            background: none;
        }
        scrollbar {
            opacity: 0.3;
        }
        scrollbar:hover {
            opacity: 0.6;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


# ─── Standalone Launch ────────────────────────────────────────────────────

def main():
    from arova.desktop.ui.scheduler import UIScheduler
    
    app = Gtk.Application(application_id="org.arova.ChatSurface")
    scheduler = UIScheduler()
    
    def on_activate(app):
        win = ArovaMainWindow(application=app, scheduler=scheduler)
        win.present()
    
    app.connect("activate", on_activate)
    app.run()


if __name__ == "__main__":
    main()
