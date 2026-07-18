import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
import cairo
from typing import List
from arova.desktop.rendering.scheduler import RenderScheduler
from arova.desktop.rendering.nodes import RenderNode

class SceneGraph(Gtk.Widget):
    """
    A custom GTK4 widget that manages rendering a tree of RenderNodes using Cairo.
    Tied directly to the RenderScheduler.
    """
    def __init__(self, scheduler: RenderScheduler):
        super().__init__()
        self.scheduler = scheduler
        self.root_nodes: List[RenderNode] = []
        
        self.scheduler.add_updatable(self.update_physics)
        self.scheduler.add_drawable(self.queue_draw)
        
    def add_node(self, node: RenderNode):
        self.root_nodes.append(node)
        
    def clear(self):
        self.root_nodes.clear()
        
    def update_physics(self, dt: float):
        # We only really need to redraw if something is moving, but for simplicity
        # we let the scheduler drive the queue_draw if physics updated.
        needs_redraw = False
        for node in self.root_nodes:
            needs_redraw |= node.update(dt)
            
        # In a hyper-optimized system, we'd only redraw if needs_redraw is True.
        # But our scheduler currently issues queue_draw unconditionally if running.

    def do_snapshot(self, snapshot):
        """
        GTK4 rendering entrypoint.
        We append a Cairo node to the Gsk.Snapshot.
        """
        width = self.get_width()
        height = self.get_height()
        
        if width <= 0 or height <= 0:
            return
            
        import graphene
        bounds = graphene.Rect().init(0, 0, width, height)
        cr = snapshot.append_cairo(bounds)
        
        # Draw background (optional, could be transparent)
        cr.set_source_rgba(0.05, 0.05, 0.05, 1.0)
        cr.paint()
        
        # Traverse scene graph
        for node in self.root_nodes:
            node.draw(cr)
