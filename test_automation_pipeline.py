"""
Quick smoke test to verify the execution pipeline works end-to-end.
Tests: EventBus -> ExecutionRuntime -> ActionDispatcher -> Backend
"""
import asyncio
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

from arova.core.events import RuntimeEventBus
from arova.core.automation.dispatcher import ActionDispatcher
from arova.core.automation.execution_runtime import ExecutionRuntime
from arova.core.automation.schema import ExecutionGraph, CapabilityRequest, RiskLevel, NodeState

async def main():
    bus = RuntimeEventBus()
    dispatcher = ActionDispatcher()
    runtime = ExecutionRuntime(event_bus=bus, dispatcher=dispatcher)
    
    print("=" * 60)
    print("TEST 1: Open Brave via EventBus")
    print("=" * 60)
    
    graph = ExecutionGraph(
        id="test_graph_1",
        goal="Open Brave Browser",
        nodes=[
            CapabilityRequest(
                id="node_1",
                action="open_app",
                capability="open_app",
                payload={"app_name": "brave"},
                expected_observation="App launched",
                success_criteria="Return code 0",
                confidence=1.0,
                confidence_reason="User explicitly requested",
                risk_level=RiskLevel.SYSTEM,
                state=NodeState.QUEUED
            )
        ]
    )
    
    bus.emit("automation", "GRAPH_EXECUTION_REQUESTED", {
        "graph": graph,
        "turn_id": "test_turn_1"
    })
    
    await asyncio.sleep(4)
    
    print("\n" + "=" * 60)
    print("TEST 2: Web Search via EventBus")
    print("=" * 60)
    
    graph2 = ExecutionGraph(
        id="test_graph_2",
        goal="Search Google",
        nodes=[
            CapabilityRequest(
                id="node_2",
                action="search_web",
                capability="search_web",
                payload={"query": "weather in Tokyo"},
                expected_observation="Web search launched",
                success_criteria="Return code 0",
                confidence=1.0,
                confidence_reason="User explicitly requested",
                risk_level=RiskLevel.SYSTEM,
                state=NodeState.QUEUED
            )
        ]
    )
    
    bus.emit("automation", "GRAPH_EXECUTION_REQUESTED", {
        "graph": graph2,
        "turn_id": "test_turn_2"
    })
    
    await asyncio.sleep(4)
    
    print("\n" + "=" * 60)
    print("TEST 3: Set Volume via EventBus")
    print("=" * 60)
    
    graph3 = ExecutionGraph(
        id="test_graph_3",
        goal="Set Volume",
        nodes=[
            CapabilityRequest(
                id="node_3",
                action="set_volume",
                capability="set_volume",
                payload={"level": 50},
                expected_observation="Volume set",
                success_criteria="Return code 0",
                confidence=1.0,
                confidence_reason="User explicitly requested",
                risk_level=RiskLevel.SYSTEM,
                state=NodeState.QUEUED
            )
        ]
    )
    
    bus.emit("automation", "GRAPH_EXECUTION_REQUESTED", {
        "graph": graph3,
        "turn_id": "test_turn_3"
    })
    
    await asyncio.sleep(4)
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
    bus.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
