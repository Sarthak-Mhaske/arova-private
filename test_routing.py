import asyncio
import logging
import time
from arova.core.providers.capabilities import Capability
from arova.core.providers.manager import ProviderManager
from arova.core.providers.policy import RoutingPolicy
from arova.core.providers.router import CapabilityRouter
from arova.core.events import RuntimeEventBus

logging.basicConfig(level=logging.INFO)

async def run():
    bus = RuntimeEventBus()
    fallbacks = []
    
    def my_cb(e):
        print("CB FIRED", repr(e))
        fallbacks.append(e)
        
    bus.subscribe("providers", "PROVIDER_FALLBACK", my_cb)
    
    pm = ProviderManager()
    policy = RoutingPolicy("hybrid")
    router = CapabilityRouter(pm, policy, bus)
    
    for name, p in pm.all_providers.items():
        if name != "mock":
            p.health.available = False
            
    active = router.get_active_routes()
    
    time.sleep(1.0)
    bus.shutdown(wait=True)
    
    print("\nFallback events emitted:", len(fallbacks))
        
if __name__ == "__main__":
    asyncio.run(run())
