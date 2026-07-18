import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from arova.desktop.rendering.scene import SceneGraph
from arova.desktop.rendering.nodes import DAGNode, SplineEdge

class SemanticMapView(Gtk.Box):
    """
    Ambient Semantic Map.
    Visualizes workspace clustering and semantic intent transitions.
    """
    def __init__(self, scheduler):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.scheduler = scheduler
        
        self.set_margin_top(16)
        self.set_margin_bottom(16)
        self.set_margin_start(16)
        self.set_margin_end(16)
        self.set_spacing(12)
        
        lbl = Gtk.Label(label="Ambient Semantic Map")
        lbl.add_css_class("title-1")
        lbl.set_halign(Gtk.Align.START)
        self.append(lbl)
        
        self.scene = SceneGraph(self.scheduler)
        self.scene.set_hexpand(True)
        self.scene.set_vexpand(True)
        self.append(self.scene)
        
        self._build_test_graph()
        
    def _build_test_graph(self):
        ws_node = DAGNode("WS: Development", "active")
        ws_node.x.target = 400
        ws_node.y.target = 200
        
        win1 = DAGNode("VSCode", "idle")
        win1.x.target = 200
        win1.y.target = 350
        
        win2 = DAGNode("Firefox", "idle")
        win2.x.target = 600
        win2.y.target = 350
        
        edge1 = SplineEdge(ws_node, win1)
        edge2 = SplineEdge(ws_node, win2)
        
        self.scene.add_node(edge1)
        self.scene.add_node(edge2)
        self.scene.add_node(ws_node)
        self.scene.add_node(win1)
        self.scene.add_node(win2)
