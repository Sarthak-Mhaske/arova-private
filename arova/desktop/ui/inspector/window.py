import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from arova.desktop.ui.scheduler import UIScheduler
from arova.desktop.rendering.scheduler import RenderScheduler

from arova.desktop.ui.inspector.timeline import TimelineView
from arova.desktop.ui.inspector.memory import MemoryView
from arova.desktop.ui.inspector.attention import AttentionView
from arova.desktop.ui.inspector.execution import ExecutionView
from arova.desktop.ui.inspector.diagnostics import DiagnosticsView
from arova.desktop.ui.inspector.semantic_map import SemanticMapView

class InspectorWindow(Gtk.ApplicationWindow):
    """
    The Cognitive Observatory & Inspector Surface.
    A developer nervous system for visualizing internal cognition.
    """
    def __init__(self, application: Gtk.Application, ui_scheduler: UIScheduler):
        super().__init__(application=application)
        self.ui_scheduler = ui_scheduler
        
        # This is the 60fps Native Cairo Render Engine 
        self.render_scheduler = RenderScheduler(target_fps=60)
        
        self.set_title("Arova Cognitive Observatory")
        self.set_default_size(1000, 700)
        
        self._build_ui()
        
    def _build_ui(self):
        # We use a leaflet or standard box with a stack sidebar
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_child(main_box)
        
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        
        self.sidebar = Gtk.StackSidebar()
        self.sidebar.set_stack(self.stack)
        self.sidebar.set_size_request(200, -1)
        
        main_box.append(self.sidebar)
        
        # Add a separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        main_box.append(sep)
        
        main_box.append(self.stack)
        
        self.timeline = TimelineView(self.ui_scheduler)
        self.stack.add_titled(self.timeline, "timeline", "Live Cognitive Timeline")
        
        self.execution = ExecutionView(self.render_scheduler)
        self.stack.add_titled(self.execution, "execution", "Execution DAG Visualizer")
        
        self.memory = MemoryView(self.render_scheduler)
        self.stack.add_titled(self.memory, "memory", "Memory Lineage Graph")
        
        self.attention = AttentionView(self.ui_scheduler)
        self.stack.add_titled(self.attention, "attention", "Attention Observatory")
        
        self.semantics = SemanticMapView(self.render_scheduler)
        self.stack.add_titled(self.semantics, "semantics", "Ambient Semantic Map")
        
        self.diagnostics = DiagnosticsView(self.ui_scheduler)
        self.stack.add_titled(self.diagnostics, "diagnostics", "Presence Diagnostics")
        
        self.connect("show", self._on_show)
        self.connect("hide", self._on_hide)
        
    def _on_show(self, widget):
        # We start the RenderScheduler for any active RenderNodes
        self.render_scheduler.start(self)
        
    def _on_hide(self, widget):
        self.render_scheduler.stop(self)
