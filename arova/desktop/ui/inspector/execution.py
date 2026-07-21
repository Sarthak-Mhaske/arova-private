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
        
        # Real event binding (no simulated test graphs in production)
        self.scheduler.bind("DAG_EXECUTION_STATE", self._on_dag_state)
        self.scheduler.bind("COGNITIVE_STREAM_STATE", self._on_cognition_stream)

    def _on_dag_state(self, event: dict):
        payload = event.get("payload", {}) if "payload" in event else event
        self.scene.clear()
        nodes = payload.get("nodes", [])
        edges = payload.get("edges", [])
        node_map = {}
        for n in nodes:
            node_obj = DAGNode(n.get("name", "NODE"), n.get("status", "idle"))
            node_obj.x.target = n.get("x", 100)
            node_obj.y.target = n.get("y", 100)
            self.scene.add_node(node_obj)
            node_map[n.get("id")] = node_obj
        for e in edges:
            src = node_map.get(e.get("source"))
            dst = node_map.get(e.get("target"))
            if src and dst:
                self.scene.add_node(SplineEdge(src, dst))

    def _on_cognition_stream(self, event: dict):
        payload = event.get("payload", {}) if "payload" in event else event
        # Dynamically update DAG node statuses if provided in stream
        step = payload.get("step")
        if step:
            node_obj = DAGNode(step, "active")
            node_obj.x.target = 250
            node_obj.y.target = 150
            self.scene.add_node(node_obj)
