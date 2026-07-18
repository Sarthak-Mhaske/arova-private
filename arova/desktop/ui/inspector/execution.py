import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from arova.desktop.rendering.scene import SceneGraph
from arova.desktop.rendering.nodes import DAGNode, SplineEdge

class ExecutionView(Gtk.Box):
    """
    Execution Graph Visualizer.
    Renders DAG execution using the Spatial Renderer.
    """
    def __init__(self, scheduler):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.scheduler = scheduler
        
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_spacing(12)
        
        lbl = Gtk.Label(label="Execution Graph Visualizer")
        lbl.add_css_class("title-1")
        lbl.set_halign(Gtk.Align.START)
        self.append(lbl)
        
        # Embedded SceneGraph for Cairo rendering
        self.scene = SceneGraph(self.scheduler)
        self.scene.set_hexpand(True)
        self.scene.set_vexpand(True)
        self.append(self.scene)
        
        # Test Graph
        self._build_test_graph()
        
    def _build_test_graph(self):
        # We simulate a cognitive DAG
        node_plan = DAGNode("PLAN", "idle")
        node_plan.x.target = 200
        node_plan.y.target = 50
        
        node_auth = DAGNode("AUTH", "paused")
        node_auth.x.target = 350
        node_auth.y.target = 150
        
        node_exec = DAGNode("EXEC", "active")
        node_exec.x.target = 500
        node_exec.y.target = 250
        
        edge1 = SplineEdge(node_plan, node_auth)
        edge2 = SplineEdge(node_auth, node_exec)
        
        # Root nodes
        self.scene.add_node(edge1)
        self.scene.add_node(edge2)
        self.scene.add_node(node_plan)
        self.scene.add_node(node_auth)
        self.scene.add_node(node_exec)
