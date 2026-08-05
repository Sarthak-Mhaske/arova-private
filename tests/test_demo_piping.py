import asyncio
import logging
from arova.core.automation.dispatcher import ActionDispatcher
from arova.core.automation.execution_runtime import ExecutionRuntime
from arova.core.automation.schema import CapabilityRequest, NodeState, RiskLevel, ExecutionGraph

logging.basicConfig(level=logging.INFO)

class DummyEventBus:
    def subscribe(self, *args, **kwargs): pass
    def emit(self, category, event, payload):
        print(f"[EVENT] {event}: {payload}")

async def run_demo():
    print("--- Starting Demo: Vision + Data Piping ---")
    
    dispatcher = ActionDispatcher()
    
    # MOCK the AnalyzeScreenBackend to pretend it successfully called Gemini
    async def mock_execute(self, request, simulation_mode=False):
        from arova.core.automation.dispatcher import BackendObservation
        # Pretend we took a screenshot and Gemini said:
        return BackendObservation("I see a large heading that says 'Welcome to Arova Automation!'", True)
    
    dispatcher._backends["analyze_screen"].execute = mock_execute.__get__(dispatcher._backends["analyze_screen"])

    event_bus = DummyEventBus()
    runtime = ExecutionRuntime(event_bus, dispatcher)
    
    node1 = CapabilityRequest(
        id="step_1",
        action="Read the browser screen",
        capability="analyze_screen",
        payload={"query": "What is the main heading on this page?"},
        expected_observation="Extracted heading text",
        success_criteria="Output is not empty",
        confidence=1.0,
        confidence_reason="Demo",
        risk_level=RiskLevel.READ,
        state=NodeState.QUEUED
    )
    
    node2 = CapabilityRequest(
        id="step_2",
        action="Echo the result",
        capability="CommandBackend",
        payload={"command": "echo 'The Vision model saw: {{step_1.output}}'"},
        expected_observation="Printed text",
        success_criteria="Return code 0",
        confidence=1.0,
        confidence_reason="Demo",
        risk_level=RiskLevel.READ,
        state=NodeState.QUEUED
    )
    
    graph = ExecutionGraph(id="demo_graph", goal="Vision Piping Demo", nodes=[node1, node2])
    
    runtime._active_graph = graph
    await runtime._execution_loop()

if __name__ == "__main__":
    asyncio.run(run_demo())
