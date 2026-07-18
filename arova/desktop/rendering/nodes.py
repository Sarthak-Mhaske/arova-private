import abc
from typing import List
from arova.desktop.rendering.physics import Spring

class RenderNode(abc.ABC):
    """
    Base class for composable Cairo drawing objects.
    """
    def __init__(self):
        self.x = Spring(0, 0)
        self.y = Spring(0, 0)
        self.alpha = Spring(1.0, 1.0)
        self.scale = Spring(1.0, 1.0)
        self.children: List['RenderNode'] = []
        
    def update(self, dt: float) -> bool:
        """Update physics. Returns True if needs redraw."""
        needs_redraw = False
        needs_redraw |= self.x.update(dt)
        needs_redraw |= self.y.update(dt)
        needs_redraw |= self.alpha.update(dt)
        needs_redraw |= self.scale.update(dt)
        
        for child in self.children:
            needs_redraw |= child.update(dt)
            
        return needs_redraw

    @abc.abstractmethod
    def draw(self, ctx):
        """Draw this node and its children using the Cairo context (ctx)."""
        pass

class DAGNode(RenderNode):
    """
    Represents a node in the execution graph.
    """
    def __init__(self, label: str, node_type: str = "default"):
        super().__init__()
        self.label = label
        self.node_type = node_type
        
    def draw(self, ctx):
        ctx.save()
        ctx.translate(self.x.value, self.y.value)
        ctx.scale(self.scale.value, self.scale.value)
        
        # Set alpha
        ctx.push_group()
        
        # Node styling based on type
        if self.node_type == "active":
            ctx.set_source_rgba(0.2, 0.6, 1.0, 1.0) # Blue pulse
        elif self.node_type == "paused":
            ctx.set_source_rgba(1.0, 0.6, 0.2, 1.0) # Orange tension
        else:
            ctx.set_source_rgba(0.3, 0.3, 0.3, 1.0) # Grey idle
            
        # Draw rounded rect / circle
        ctx.arc(0, 0, 20, 0, 6.28)
        ctx.fill()
        
        # Text
        ctx.set_source_rgba(1, 1, 1, 1)
        ctx.select_font_face("Inter", 0, 0) # Normal, Normal
        ctx.set_font_size(10)
        extents = ctx.text_extents(self.label)
        ctx.move_to(-(extents.width/2), extents.height/2)
        ctx.show_text(self.label)
        
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(self.alpha.value)
        ctx.restore()
        
        for child in self.children:
            child.draw(ctx)

class SplineEdge(RenderNode):
    """
    Draws a flowing bezier curve between two nodes.
    """
    def __init__(self, start_node: RenderNode, end_node: RenderNode):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node
        
    def draw(self, ctx):
        ctx.save()
        ctx.set_source_rgba(0.5, 0.5, 0.5, self.alpha.value * 0.5)
        ctx.set_line_width(2.0)
        
        sx, sy = self.start_node.x.value, self.start_node.y.value
        ex, ey = self.end_node.x.value, self.end_node.y.value
        
        # Simple bezier control points for a downward/rightward flowing DAG
        ctx.move_to(sx, sy)
        ctx.curve_to(sx, (sy + ey) / 2, ex, (sy + ey) / 2, ex, ey)
        
        ctx.stroke()
        ctx.restore()
