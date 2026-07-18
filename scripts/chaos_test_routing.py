import time
import logging
import asyncio
from arova.core.models.orchestrator import ModelOrchestrator
from arova.core.models.profiles import CognitiveProfile
from arova.core.models.schema import ReasoningDepth, ReasoningBudget

logging.basicConfig(level=logging.INFO)

async def run_routing_chaos():
    logging.info("Starting Phase 12A.5 Routing Chaos Test")
    
    # Initialize with default config (empty is fine for this test)
    orchestrator = ModelOrchestrator(config={}, active_profile=CognitiveProfile.BALANCED)
    
    # 1. Normal Routing Test
    logging.info("Test 1: Routing Deep Task under Balanced Profile (Expect Cloud/Groq unless budget limited)")
    # Should route to Groq
    adapter, model = orchestrator.router.route(ReasoningDepth.DEEP, ReasoningBudget(max_tokens=500), CognitiveProfile.BALANCED)
    logging.info(f"Routed to: {adapter.provider_name} ({model})")
    assert adapter.provider_name == "groq"
    
    # 2. Budget Constrained Test
    logging.info("Test 2: Routing Deep Task under Minimal Profile (Expect Local/Ollama)")
    adapter, model = orchestrator.router.route(ReasoningDepth.DEEP, ReasoningBudget(max_tokens=500), CognitiveProfile.MINIMAL)
    logging.info(f"Routed to: {adapter.provider_name} ({model})")
    assert adapter.provider_name == "ollama"
    
    # 3. Offline Degradation Simulation
    logging.info("Test 3: Simulating Offline Mode (Force OFFLINE_FIRST profile)")
    adapter, model = orchestrator.router.route(ReasoningDepth.STANDARD, ReasoningBudget(max_tokens=100), CognitiveProfile.OFFLINE_FIRST)
    logging.info(f"Routed to: {adapter.provider_name} ({model})")
    assert adapter.provider_name == "ollama"
    
    logging.info("Routing Chaos Test Passed. Federation layer handles constraints gracefully.")

if __name__ == "__main__":
    asyncio.run(run_routing_chaos())
