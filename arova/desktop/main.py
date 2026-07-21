import sys
import asyncio
import json
import logging
import threading
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

from arova.desktop.ui.scheduler import UIScheduler
from arova.desktop.ui.orb.presence_orb import PresenceOrb
from arova.desktop.ui.narrative.feed import NarrativeFeed
from arova.desktop.ui.overlays.approval import ApprovalOverlay
from arova.desktop.ui.inspector.window import InspectorWindow

logging.basicConfig(level=logging.INFO)

class ArovaViewModel:
    def __init__(self, socket_path: str, scheduler: UIScheduler):
        self.socket_path = socket_path
        self.scheduler = scheduler
        self._reader = None
        self._writer = None
        self.scheduler.send_callback = self._send_payload

    def _send_payload(self, payload: dict):
        if self._writer:
            try:
                data = (json.dumps(payload) + "\n").encode('utf-8')
                self._writer.write(data)
                asyncio.create_task(self._writer.drain())
            except Exception as e:
                logging.error(f"Failed to send IPC payload: {e}")
        else:
            logging.warning("ArovaViewModel: IPC writer not connected.")

    async def connect_and_listen(self):
        try:
            self._reader, self._writer = await asyncio.open_unix_connection(self.socket_path)
            logging.info("Connected to Arova daemon")
            self.scheduler.dispatch_ipc_event({"event_type": "CONNECTION_STATUS", "status": "connected"})
            
            while True:
                line = await self._reader.readline()
                if not line:
                    break
                try:
                    payload = json.loads(line.decode('utf-8'))
                    self.scheduler.dispatch_ipc_event(payload)
                except json.JSONDecodeError as e:
                    logging.warning(f"Received malformed JSON payload over IPC socket: {e}")
        except Exception as e:
            logging.error(f"Failed to connect: {e}")
            self.scheduler.dispatch_ipc_event({"event_type": "CONNECTION_STATUS", "status": "disconnected", "error": str(e)})

class SurfaceSystem(Gtk.Application):
    def __init__(self, scheduler: UIScheduler):
        super().__init__(application_id="org.sarthak.ArovaShell")
        self.scheduler = scheduler
        
        # We will hold references to our surface windows here.
        # In a real Gtk4LayerShell environment, these would be layer windows.
        self._orb_surface = None
        self._approval_overlay = None
        self._narrative_feed = None
        self._inspector_window = None
        
        self.scheduler.bind("CONNECTION_STATUS", self._on_connection)
        self.scheduler.bind("TOGGLE_INSPECTOR", self._on_toggle_inspector)
        
    def do_activate(self):
        logging.info("Surface System Activated. Booting cognitive surfaces...")
        
        # 1. Narrative Feed (Bottom Left)
        self._narrative_feed = NarrativeFeed(self, self)
        
        # 2. Approval Overlay (Top Right)
        self._approval_overlay = ApprovalOverlay(self, self)
        
        # 3. Presence Orb (Center or Bottom)
        self.orb_win = Gtk.ApplicationWindow(application=self, title="Arova Orb")
        self.orb_win.set_decorated(False)
        self.orb = PresenceOrb(self.scheduler)
        self.orb.set_halign(Gtk.Align.CENTER)
        self.orb.set_valign(Gtk.Align.CENTER)
        self.orb_win.set_child(self.orb)
        self.orb_win.set_default_size(120, 120)
        
        try:
            gi.require_version('Gtk4LayerShell', '1.0')
            from gi.repository import Gtk4LayerShell
            Gtk4LayerShell.init_for_window(self.orb_win)
            Gtk4LayerShell.set_layer(self.orb_win, Gtk4LayerShell.Layer.OVERLAY)
            Gtk4LayerShell.set_anchor(self.orb_win, Gtk4LayerShell.Edge.BOTTOM, True)
            Gtk4LayerShell.set_margin(self.orb_win, Gtk4LayerShell.Edge.BOTTOM, 20)
        except (ValueError, ImportError):
            pass
            
        self.orb_win.present()
        
    def _on_toggle_inspector(self, event: dict):
        if not self._inspector_window:
            self._inspector_window = InspectorWindow(self, self.scheduler)
            
        if self._inspector_window.is_visible():
            self._inspector_window.hide()
        else:
            self._inspector_window.present()

    def _on_connection(self, event: dict):
        logging.info(f"Connection Status: {event.get('status')}")

def main():
    scheduler = UIScheduler()
    vm = ArovaViewModel("/tmp/arova.sock", scheduler)
    
    def start_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(vm.connect_and_listen())
        
    t = threading.Thread(target=start_loop, daemon=True)
    t.start()
    
    app = SurfaceSystem(scheduler)
    app.run(sys.argv)

if __name__ == "__main__":
    main()
