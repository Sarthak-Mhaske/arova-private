import asyncio
import websockets
import json

async def run_test():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        print("Connected.")
        
        msg = {
            "type": "user.message",
            "text": "hello test",
            "vocalize": False
        }
        await websocket.send(json.dumps(msg))
        print("Sent user.message")
        
        while True:
            response = await websocket.recv()
            print(f"Received: {response}")
            data = json.loads(response)
            if data.get("type") == "voice.response" or data.get("type") == "projection.updated":
                pass

asyncio.run(run_test())
