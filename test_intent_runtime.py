import asyncio
from arova.core.session import ConversationSession
from arova.core.events import RuntimeEventBus, DictPayload
from arova.core.voice.intent_runtime import IntentRuntime

class MockConfig:
    pass

def test():
    eb = RuntimeEventBus()
    session = ConversationSession()
    runtime = IntentRuntime(MockConfig(), eb, session)
    
    turn = session.start_new_turn("sup")
    
    payload = DictPayload(
        data={"transcript": "sup"},
        turn_id=turn.turn_id
    )
    
    try:
        runtime._on_transcript("voice", "TRANSCRIPT_FINAL", payload)
        print("Success")
    except Exception as e:
        print(f"Exception: {e.__class__.__name__}: {e}")

if __name__ == '__main__':
    test()
