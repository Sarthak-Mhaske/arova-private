from arova.core.session import ConversationSession

def test():
    session = ConversationSession()
    
    turn = session.start_new_turn("hello")
    turn_id = turn.turn_id
    
    print(f"Authoritative ID: {session.get_authoritative_turn_id()}")
    print(f"Is authoritative? {session.is_authoritative(turn_id)}")
    
    # Simulate intent_runtime.py
    if not turn_id or not session.is_authoritative(turn_id):
        print("Calling start_new_turn AGAIN!")
        session.start_new_turn("hello")
    else:
        print("Not calling start_new_turn again.")
        
    print(f"Legacy messages: {len(session._legacy_messages)}")

if __name__ == '__main__':
    test()
