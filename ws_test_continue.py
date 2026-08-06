import asyncio
import websockets
import json

async def test():
    uri = "ws://localhost:33003"
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to Arova daemon!")
            # send ping
            await websocket.send(json.dumps({"type": "runtime.ping"}))
            # wait for messages
            for _ in range(5):
                msg = await websocket.recv()
                data = json.loads(msg)
                print("Received:", data.get("type"))
                if data.get("type") == "cognition.surfacing_push":
                    print("Surfacing push payload:", json.dumps(data, indent=2))
                if data.get("type") == "session.sync":
                    print("Session sync received.")
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
