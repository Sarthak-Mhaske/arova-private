import asyncio
import json
from pathlib import Path
from arova.core.runtime import RuntimeContainer

async def test_delete():
    r = RuntimeContainer()
    
    threads_before = list(r.session.thread_manager._threads.keys())
    print(f"Threads before: {threads_before}")
    
    if not threads_before:
        print("No threads to delete.")
        return
        
    thread_id = threads_before[0]
    print(f"Deleting thread: {thread_id}")
    r.session.thread_manager.delete_thread(thread_id)
    r._persist_runtime()
    
    with open(Path("~/.arova/runtime/current.json").expanduser(), "r") as f:
        data = json.load(f)
        
    threads_after = [t["thread_id"] for t in data["hot_state"]["active_threads"]]
    print(f"Threads in current.json after delete: {threads_after}")

if __name__ == '__main__':
    asyncio.run(test_delete())
