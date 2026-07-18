import logging

class CognitiveStreamLayer:
    """
    Converts raw internal architecture transitions into polished Cognitive Surface States.
    Emits these via IPC to the UI.
    """
    def __init__(self, event_bus):
        self.event_bus = event_bus
        
    def stream_state(self, internal_event: str, details: dict = None):
        """
        Maps raw daemon events to atmospheric text.
        """
        surface_state = self._map_event_to_surface(internal_event, details or {})
        if surface_state:
            logging.debug(f"[CognitiveStream] Emitting state: {surface_state}")
            self.event_bus.publish("COGNITIVE_STREAM_STATE", {
                "text": surface_state
            })
            
    def _map_event_to_surface(self, event: str, details: dict) -> str:
        # Prevent raw chain of thought streaming. Use atmospheric abstractions.
        if event == "MEMORY_SEARCH_START":
            return "Retrieving related context..."
        elif event == "MEMORY_SEARCH_HIT":
            return "Synthesizing prior semantic state..."
        elif event == "ROUTING_TO_CLOUD":
            return "Delegating deep planning..."
        elif event == "ROUTING_TO_EDGE":
            return "Evaluating local constraints..."
        elif event == "EVALUATING_TRUST_POLICY":
            return "Verifying execution safety boundaries..."
        elif event == "AUTOMATION_GRAPH_BUILDING":
            return "Preparing workflow graph..."
        elif event == "AUTOMATION_GRAPH_WAITING_AUTH":
            return "Awaiting execution authorization."
        return None
