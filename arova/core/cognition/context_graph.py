import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class ContextKnowledgeGraph:
    """
    Cross-Application Context Knowledge Graph for Arova.
    Connects code files, YouTube videos, documentation tabs, and terminal commands
    into an interconnected memory web for natural language query retrieval.
    """
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []

    def add_resource(self, identity: str, r_type: str, title: str, category: str = "general"):
        self.nodes[identity] = {
            "identity": identity,
            "type": r_type,
            "title": title,
            "category": category,
            "timestamp": time.time()
        }

    def link_resources(self, source_id: str, target_id: str, relation: str = "associated_with"):
        if source_id in self.nodes and target_id in self.nodes:
            self.edges.append({
                "source": source_id,
                "target": target_id,
                "relation": relation,
                "timestamp": time.time()
            })

    def query_context(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Finds connected resources matching a query term.
        e.g. 'what video was I watching when editing async_demo.py?'
        """
        results = []
        term_lower = search_term.lower()

        # Find matching node
        matched_keys = [k for k, node in self.nodes.items() if term_lower in k.lower() or term_lower in node.get("title", "").lower()]
        
        for k in matched_keys:
            # Find all linked resources via edges
            for edge in self.edges:
                if edge["source"] == k:
                    target_node = self.nodes.get(edge["target"])
                    if target_node:
                        results.append(target_node)
                elif edge["target"] == k:
                    source_node = self.nodes.get(edge["source"])
                    if source_node:
                        results.append(source_node)

        # Fallback to direct title matches
        if not results:
            results = [node for k, node in self.nodes.items() if any(w in node.get("title", "").lower() for w in term_lower.split() if len(w) > 3)]

        return results[:5]
