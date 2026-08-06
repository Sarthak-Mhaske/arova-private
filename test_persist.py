import asyncio
import json
import traceback
from pathlib import Path
from arova.core.runtime import RuntimeContainer

async def test_persist():
    print("Loading RuntimeContainer...")
    r = RuntimeContainer()
    print("RuntimeContainer initialized!")
    
    # Try calling _persist_runtime to see if it throws!
    try:
        print("Calling _persist_runtime()...")
        r._persist_runtime()
        print("Success! _persist_runtime() did not throw.")
    except Exception as e:
        print(f"FAILED TO PERSIST! Exception: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_persist())
