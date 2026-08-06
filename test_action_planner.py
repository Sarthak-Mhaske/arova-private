import asyncio
import logging
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

from arova.core.models.orchestrator import ModelOrchestrator
from arova.core.models.profiles import CognitiveProfile
from arova.core.cognition.action_planner import ActionPlanner
from arova.core.cognition.context import CognitiveContext
from arova.core.models.schema import ReasoningBudget
from arova.core.config.manager import get_config_manager

async def main():
    config = get_config_manager().load_config()
    orchestrator = ModelOrchestrator(config, active_profile=CognitiveProfile.BALANCED)
    planner = ActionPlanner(orchestrator)
    
    print("=" * 60)
    print("TEST: Multi-tool request")
    print("=" * 60)
    
    messages = [
        {"role": "user", "content": "Mute the volume, open up Brave, and search Google for the latest artificial intelligence news"}
    ]
    class DummyContext:
        def to_system_prompt_block(self):
            return "CONTEXT: None"
    context = DummyContext()
    
    result = await planner.generate_action_plan(messages, context, ReasoningBudget(max_tokens=300))
    if result:
        graph, feedback = result
        print(f"\nFEEDBACK: {feedback}")
        print("\nGRAPH NODES:")
        for n in graph.nodes:
            print(f"- {n.capability_name}: {n.args}")
    else:
        print("FAILED to generate action plan")

if __name__ == "__main__":
    asyncio.run(main())
