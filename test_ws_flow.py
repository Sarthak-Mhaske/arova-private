import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://127.0.0.1:8765") as ws:
        # Wait for the initial session.sync
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("type") == "session.sync":
                print("Initial sync:", data["messages"])
                break
        
        # Send a user message
        await ws.send(json.dumps({
            "type": "user.message",
            "text": "Bro lets get back to the work",
            "vocalize": False
        }))
        
        # Wait a bit
        await asyncio.sleep(4)
        
        # Request sync again
        await ws.send(json.dumps({
            "type": "session.sync_request"
        }))
        
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("type") == "session.sync":
                print("\nSync after message:", data["messages"])
                break
                
asyncio.run(test())
