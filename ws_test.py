import asyncio
import websockets
import json

async def test():
    async with websockets.connect("ws://127.0.0.1:8765") as ws:
        await ws.send(json.dumps({"type": "session.sync_request"}))
        response = await ws.recv()
        data = json.loads(response)
        if data.get("type") == "session.sync":
            print("Received session.sync messages:")
            for m in data.get("messages", []):
                print(f"Role: {m.get('role')} | ID: {m.get('id')} | Content: {m.get('content')[:50]}...")
                
asyncio.run(test())
