import asyncio
from arova.core.events import RuntimeEventBus

def test():
    bus = RuntimeEventBus()
    
    events_received = []
    def on_event(payload):
        events_received.append(payload)
    
    bus.subscribe("test", "EVENT", on_event)
    
    
    bus.emit("test", "EVENT", {"transcript": "hello", "turn_id": "turn_123"})
    
    import time
    time.sleep(0.1)
    bus.shutdown(wait=True)
    
    if events_received:
        payload = events_received[0]
        print(f"turn_id from dict: {payload.data.get('turn_id')}")
        print(f"turn_id from attr: {payload.turn_id}")
    else:
        print("No events received.")
    
if __name__ == '__main__':
    test()
