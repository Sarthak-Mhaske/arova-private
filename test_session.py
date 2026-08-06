from arova.core.session import ConversationSession

def test():
    session = ConversationSession()
    
    # User types "sup"
    turn1 = session.start_new_turn("sup")
    session.add_assistant_message("You're back...")
    
    # User types "hello"
    turn2 = session.start_new_turn("hello")
    session.add_assistant_message("How can I help?")
    
    for msg in session._legacy_messages:
        print(f"{msg['role']}: {msg['content']}")
        
if __name__ == '__main__':
    test()
