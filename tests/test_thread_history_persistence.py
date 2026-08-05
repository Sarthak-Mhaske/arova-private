import pytest
from arova.core.session import ConversationSession

def test_thread_history_saving_and_restoration():
    session = ConversationSession()
    
    # 1. Simulate active chat messages
    turn1 = session.start_new_turn("Explain quantum entanglement")
    session.end_active_turn("Quantum entanglement is a phenomenon where particles share quantum states...")
    
    assert len(session._legacy_messages) == 2
    
    # 2. Create a new thread (saving old chat)
    thread = session.thread_manager.create_thread("Quantum Discussion")
    thread.messages = list(session._legacy_messages)
    
    # Reset active session for fresh chat
    session.clear()
    assert len(session._legacy_messages) == 0
    
    # 3. Simulate new chat session
    session.start_new_turn("How do I configure Vite?")
    session.end_active_turn("Vite can be configured in vite.config.ts...")
    assert len(session._legacy_messages) == 2
    
    # 4. Resume old thread
    session.thread_manager.resume_thread(thread.thread_id)
    
    # 5. Assert old messages are restored cleanly
    assert len(session._legacy_messages) == 2
    assert session._legacy_messages[0]["content"] == "Explain quantum entanglement"
    assert "Quantum entanglement is a phenomenon" in session._legacy_messages[1]["content"]

def test_runtime_projector_includes_latent_threads():
    from arova.core.projection.projector import RuntimeProjector
    session = ConversationSession()
    
    session.start_new_turn("Explain neural networks")
    session.end_active_turn("Neural networks are computing systems inspired by biological brains...")
    
    thread = session.thread_manager.create_thread("Neural Nets")
    thread.messages = list(session._legacy_messages)
    session.thread_manager.update_thread_state(thread.thread_id, "latent")
    
    projector = RuntimeProjector(session_manager=session, thread_manager=session.thread_manager)
    projection = projector.project()
    
    visible_thread = next((t for t in projection.visible_threads if t.thread_id == thread.thread_id), None)
    assert visible_thread is not None
    assert visible_thread.state == "latent"
    assert len(visible_thread.messages) == 2
    assert visible_thread.messages[0]["content"] == "Explain neural networks"
