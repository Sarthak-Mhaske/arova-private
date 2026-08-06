import asyncio
from arova.core.voice.intent_runtime import IntentRuntime
from arova.core.session import ConversationSession
from arova.core.events import RuntimeEventBus

async def main():
    bus = RuntimeEventBus()
    runtime = IntentRuntime(bus)
    session = ConversationSession()
    runtime.set_session(session)
    
    # Let's mock a workspace manager to get the prompt
    class DummyWS:
        def get_workspace_summary_prompt(self):
            return "User's Active Project: Arova Development\nDomain: engineering"
    class DummyWSManager:
        def get_active_workspace(self):
            return DummyWS()
            
    runtime._workspace_manager = DummyWSManager()
    
    # We can't easily run process_transcript_cognition without mocking a lot, 
    # but we can just grep the whole arova directory for `"actions": null` or `"context": {` to see if there's a few-shot prompt.
    pass
