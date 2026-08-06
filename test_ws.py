import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://127.0.0.1:8765"
    async with websockets.connect(uri) as websocket:
        print("Connected.")
        
        # Read the initial status event
        status = await websocket.recv()
        print(f"< {status}")
        
        # Send user.message
        payload = {
            "type": "user.message",
            "text": "test double message",
            "vocalize": False
        }
        print(f"> {payload}")
        await websocket.send(json.dumps(payload))
        
        # Read all responses for 2 seconds
        end_time = asyncio.get_event_loop().time() + 2.0
        while True:
            timeout = end_time - asyncio.get_event_loop().time()
            if timeout <= 0:
                break
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                print(f"< {response}")
            except asyncio.TimeoutError:
                break

asyncio.run(test_ws())
