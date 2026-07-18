import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from arova.desktop.rendering.scene import SceneGraph
from arova.desktop.rendering.nodes import DAGNode, SplineEdge

class MemoryView(Gtk.Box):
    """
    Memory Lineage Graph.
    Visualizes memory retrieval logic and semantic relationships.
    """
    def __init__(self, scheduler):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.scheduler = scheduler
        
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_spacing(12)
        
        lbl = Gtk.Label(label="Memory Lineage Graph")
        lbl.add_css_class("title-1")
        lbl.set_halign(Gtk.Align.START)
        self.append(lbl)
        
        self.scene = SceneGraph(self.scheduler)
        self.scene.set_hexpand(True)
        self.scene.set_vexpand(True)
        self.append(self.scene)
        
        self._build_test_graph()
        
    def _build_test_graph(self):
        # Center target
        query_node = DAGNode("QUERY", "active")
        query_node.x.target = 400
        query_node.y.target = 300
        
        mem1 = DAGNode("MEM: Setup", "idle")
        mem1.x.target = 200
        mem1.y.target = 150
        
        mem2 = DAGNode("MEM: Project", "idle")
        mem2.x.target = 600
        mem2.y.target = 150
        
        edge1 = SplineEdge(mem1, query_node)
        edge2 = SplineEdge(mem2, query_node)
        
        self.scene.add_node(edge1)
        self.scene.add_node(edge2)
        self.scene.add_node(query_node)
        self.scene.add_node(mem1)
        self.scene.add_node(mem2)
