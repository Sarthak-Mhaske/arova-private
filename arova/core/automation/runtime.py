import logging
import uuid
import asyncio
from typing import Dict, List, Any
from arova.core.events import RuntimeEventBus, EventPayload
from arova.core.automation.graph import GraphDefinition
from arova.core.automation.runner import GraphRunner
from arova.core.ambience.schema import AmbientContext

class AutomationRuntime:
    """
    Coordinates graphs and triggers. Listens to ambient changes and 
    voice commands to spawn GraphRunners.
    """
    def __init__(self, event_bus: RuntimeEventBus):
        self.event_bus = event_bus
        self.registered_graphs: Dict[str, GraphDefinition] = {}
        self.active_runners: Dict[str, GraphRunner] = {}
        
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
            
        self.event_bus.subscribe("ambience", "CONTEXT_CHANGED", self._on_context_changed)
        
    def register_graph(self, graph: GraphDefinition):
        self.registered_graphs[graph.id] = graph
        logging.info(f"Registered Automation Graph: {graph.id}")

    def spawn_graph(self, graph_id: str) -> str:
        if graph_id not in self.registered_graphs:
            raise ValueError(f"Unknown graph: {graph_id}")
            
        exec_id = str(uuid.uuid4())
        runner = GraphRunner(self.event_bus, self.registered_graphs[graph_id], exec_id)
        self.active_runners[exec_id] = runner
        runner.start()
        
        # Cleanup when done
        async def _wait_and_cleanup():
            while runner._running:
                await asyncio.sleep(1.0)
            self.active_runners.pop(exec_id, None)
            
        if self._loop:
            asyncio.run_coroutine_threadsafe(_wait_and_cleanup(), self._loop)
        else:
            logging.error("AutomationRuntime: No event loop captured at initialization!")
        return exec_id

    def _on_context_changed(self, payload: EventPayload):
        raw_ctx = getattr(payload, "context_snapshot", {})
        # Note: We reconstruct AmbientContext here just to validate, but the dict works fine
        
        active_app = raw_ctx.get("active_app")
        # Extremely basic triggering for Phase 6
        # In the future, this involves the TriggerEngine and Confidence Scoring
        if active_app == "kitty" and "mock_terminal_automation" in self.registered_graphs:
            # Prevent infinite loops if already running
            already_running = False
            for runner in self.active_runners.values():
                if runner.graph.id == "mock_terminal_automation":
                    already_running = True
                    break
                    
            if not already_running:
                logging.info(f"Ambient Context triggered automation: mock_terminal_automation")
                self.spawn_graph("mock_terminal_automation")
