#!/usr/bin/env python3
"""
Arova Graph Inspector — Runtime Observability CLI

Connects to the Arova daemon via UDS and continuously renders
the SemanticEnvironmentGraph snapshot to the terminal.

Usage:
    python -m arova.tools.graph_inspector          # one-shot snapshot
    python -m arova.tools.graph_inspector --watch   # live polling every 2s
"""
import asyncio
import json
import sys
import os
import time

SOCKET_PATH = "/tmp/arova.sock"
POLL_INTERVAL = 2.0

# ANSI colors for terminal rendering
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[36m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
MAGENTA = "\033[35m"


async def query_snapshot() -> dict:
    """Connect to the Arova daemon UDS and request the environment graph snapshot."""
    reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
    
    request = json.dumps({"command": "environment.snapshot"}) + "\n"
    writer.write(request.encode("utf-8"))
    await writer.drain()
    
    line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    
    if not line:
        return {"error": "empty response"}
    return json.loads(line.decode("utf-8"))


def render_snapshot(data: dict):
    """Render the graph snapshot to the terminal with color coding."""
    os.system("clear" if os.name != "nt" else "cls")
    
    print(f"{BOLD}{CYAN}╔══════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{CYAN}║   AROVA — Semantic Environment Graph Inspector  ║{RESET}")
    print(f"{BOLD}{CYAN}╚══════════════════════════════════════════════════╝{RESET}")
    print()
    
    if "error" in data:
        print(f"  {RED}Error: {data['error']}{RESET}")
        return
    
    snapshot = data.get("snapshot", {})
    trace = data.get("trace", [])
    
    # Derived state (high-level synthesis)
    derived = snapshot.pop("_derived", {})
    if derived:
        print(f"  {BOLD}{GREEN}── Derived State ──{RESET}")
        print(f"    Workspace Type:    {BOLD}{derived.get('current_workspace_type', '?')}{RESET}")
        print(f"    Attention Mode:    {BOLD}{_color_mode(derived.get('probable_attention_mode', '?'))}{RESET}")
        print(f"    Focus Depth:       {_render_bar(derived.get('active_focus_depth', 0))}")
        print(f"    Active Nodes:      {derived.get('graph_node_count', 0)}")
        print()
    
    # Active nodes
    if snapshot:
        print(f"  {BOLD}{YELLOW}── Active Nodes ──{RESET}")
        for stype, node in snapshot.items():
            conf = node.get("confidence", 0)
            age = node.get("age_s", 0)
            source = node.get("source", "?")
            conf_bar = _render_bar(conf)
            age_str = f"{age:.0f}s ago" if age < 120 else f"{age/60:.1f}m ago"
            
            print(f"    {CYAN}{stype}{RESET}")
            print(f"      Confidence: {conf_bar}  ({conf:.3f})")
            print(f"      Age:        {DIM}{age_str}{RESET}")
            print(f"      Source:     {DIM}{source}{RESET}")
            print()
    else:
        print(f"  {DIM}  (no active nodes — room is quiet){RESET}")
        print()
    
    # Recent trace
    if trace:
        print(f"  {BOLD}{MAGENTA}── Event Trace (last {len(trace)}) ──{RESET}")
        for entry in trace[-8:]:
            ts = time.strftime("%H:%M:%S", time.localtime(entry.get("timestamp", 0)))
            print(f"    {DIM}{ts}{RESET}  {entry.get('semantic_type', '?')}  {DIM}src={entry.get('source', '?')}{RESET}")
        print()
    
    print(f"  {DIM}Polled at {time.strftime('%H:%M:%S')}{RESET}")


def _color_mode(mode: str) -> str:
    colors = {
        "deep_work": f"{GREEN}{mode}{RESET}",
        "active": f"{YELLOW}{mode}{RESET}",
        "fragmented": f"{RED}{mode}{RESET}",
        "idle": f"{DIM}{mode}{RESET}",
    }
    return colors.get(mode, mode)


def _render_bar(value: float, width: int = 20) -> str:
    filled = int(value * width)
    empty = width - filled
    bar = f"{GREEN}{'█' * filled}{DIM}{'░' * empty}{RESET}"
    return f"[{bar}]"


async def main():
    watch = "--watch" in sys.argv
    
    if not os.path.exists(SOCKET_PATH):
        print(f"{RED}Error: Arova daemon not running (no socket at {SOCKET_PATH}){RESET}")
        sys.exit(1)
    
    if watch:
        while True:
            try:
                data = await query_snapshot()
                render_snapshot(data)
            except Exception as e:
                print(f"{RED}Connection error: {e}{RESET}")
            await asyncio.sleep(POLL_INTERVAL)
    else:
        data = await query_snapshot()
        render_snapshot(data)


if __name__ == "__main__":
    asyncio.run(main())
