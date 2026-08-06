import asyncio
import sys

from arova.core.session import ConversationSession
from arova.core.events import RuntimeEventBus, DictPayload
from arova.core.voice.intent_runtime import IntentRuntime
from arova.core.providers.router import CognitiveRouter
from arova.core.cognition.planner import CognitivePlanner
from arova.core.cognition.context import RuntimeContextSynthesizer
from arova.core.models.runtime import ModelOrchestrator

class MockConfig:
    def get(self, *args, **kwargs):
        return None

def test():
    eb = RuntimeEventBus()
    session = ConversationSession()
    config = MockConfig()
    
    # Just mock objects for the dependencies
    class MockRouter:
        async def route(self, messages): pass
    
    class MockSynthesizer:
        pass
        
    class MockPlanner:
        pass

    router = MockRouter()
    context_synthesizer = MockSynthesizer()
    planner = MockPlanner()

    runtime = IntentRuntime(
        event_bus=eb,
        session=session,
        router=router,
        context_synthesizer=context_synthesizer,
        planner=planner,
        config=config
    )
    
    # Needs a loop to submit task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    runtime._loop = loop
    
    turn = session.start_new_turn("sup")
    
    payload = DictPayload(
        data={"transcript": "sup", "turn_id": turn.turn_id},
        turn_id=turn.turn_id
    )
    
    print("Calling _on_transcript")
    runtime._on_transcript(payload)
    
    # run loop briefly
    loop.call_later(1.0, loop.stop)
    loop.run_forever()

if __name__ == '__main__':
    test()
