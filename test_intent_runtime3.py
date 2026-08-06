import asyncio

from arova.core.session import ConversationSession
from arova.core.events import RuntimeEventBus, DictPayload
from arova.core.voice.intent_runtime import IntentRuntime

class MockRouter:
    async def route(self, messages): pass

class MockSynthesizer:
    pass

class MockPlanner:
    pass

def test():
    eb = RuntimeEventBus()
    session = ConversationSession()
    
    runtime = IntentRuntime(
        event_bus=eb,
        session=session,
        router=MockRouter(),
        context_synthesizer=MockSynthesizer(),
        planner=MockPlanner()
    )
    
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
    
    def on_done():
        loop.stop()
        
    loop.call_later(1.0, on_done)
    loop.run_forever()

if __name__ == '__main__':
    test()
