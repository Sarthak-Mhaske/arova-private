from arova.core.events import DictPayload

def test():
    payload = DictPayload(data={"transcript": "hello", "turn_id": "123"})
    
    try:
        if "data" in payload:
            print("It works!")
    except Exception as e:
        print(f"Exception: {e.__class__.__name__}: {e}")

if __name__ == '__main__':
    test()
