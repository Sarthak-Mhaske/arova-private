from arova.core.events import EventPayload, DictPayload

def test():
    data = {"transcript": "hello", "turn_id": "turn_123"}
    payload = DictPayload(data=data, turn_id="turn_123")
    
    try:
        print("Trying payload.get...")
        val = payload.get("transcript", "")
        print(f"Success! {val}")
    except Exception as e:
        print(f"Exception: {e.__class__.__name__}: {e}")

if __name__ == '__main__':
    test()
