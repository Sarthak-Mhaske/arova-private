import sys
import asyncio
from unittest.mock import MagicMock
sys.path.insert(0, "/home/sarthak/arova")

# Actually, the easiest way to test this is to just run a script that manually loads current.json, modifies the workspace to add a dummy file, saves it, and then we restart arovad and look at the UI.
import json
import time
from pathlib import Path

path = Path("/home/sarthak/.arova/runtime/current.json")
if path.exists():
    with open(path, "r") as f:
        data = json.load(f)
    
    # modify ws_default
    ws_default = data.get("hot_state", {}).get("workspaces", {}).get("ws_default", {})
    if ws_default:
        ws_default["reality"]["resources"]["/home/sarthak/arova/super_new_test_file.py"] = {
            "identity": "/home/sarthak/arova/super_new_test_file.py",
            "type": "file",
            "last_seen": time.time(),
            "summary": "Testing recovery"
        }
        # ensure repo_paths is empty to trigger the buggy branch (which should now be fixed)
        ws_default["interpretation"]["repo_paths"] = []
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print("Injected super_new_test_file.py into current.json and wiped repo_paths!")
    else:
        print("ws_default not found in current.json")
else:
    print("current.json not found")
