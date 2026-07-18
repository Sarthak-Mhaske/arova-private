#!/usr/bin/env python3
"""
Arova Runtime Observer — Cognitive Debugging CLI

Connects to the Arova daemon via UDS and continuously renders
the CognitivePriorityEngine, AttentionTrajectory, and PresenceModulator state.

Usage:
    python -m arova.tools.runtime_observer          # one-shot
    python -m arova.tools.runtime_observer --watch  # live polling
"""
import asyncio
import json
import sys
import os
import time

SOCKET_PATH = "/tmp/arova.sock"
POLL_INTERVAL = 2.0

# ANSI colors
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
CYAN    = "\033[36m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
RED     = "\033[31m"
MAGENTA = "\033[35m"
BLUE    = "\033[34m"

async def query_cognition() -> dict:
    reader, writer = await asyncio.open_unix_connection(SOCKET_PATH)
    request = json.dumps({"command": "cognition.snapshot"}) + "\n"
    writer.write(request.encode("utf-8"))
    await writer.drain()
    
    line = await reader.readline()
    writer.close()
    await writer.wait_closed()
    
    if not line:
        return {"error": "empty response"}
    return json.loads(line.decode("utf-8"))

def _render_bar(value: float, width: int = 15) -> str:
    filled = int(value * width)
    empty = width - filled
    bar = f"{'█' * filled}{DIM}{'░' * empty}{RESET}"
    return f"[{bar}]"

def render_snapshot(data: dict):
    os.system("clear" if os.name != "nt" else "cls")
    
    print(f"{BOLD}{MAGENTA}╔════════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}{MAGENTA}║      AROVA — Cognitive Synthesis Runtime Observer      ║{RESET}")
    print(f"{BOLD}{MAGENTA}╚════════════════════════════════════════════════════════╝{RESET}")
    print()
    
    if "error" in data:
        print(f"  {RED}Error: {data['error']}{RESET}")
        return
        
    trajectory = data.get("trajectory", {})
    modulation = data.get("modulation", {})
    priority = data.get("priority_engine", {})
    
    # 1. Attention Trajectory
    print(f"  {BOLD}{CYAN}── ATTENTION TRAJECTORY ──{RESET}")
    if trajectory:
        print(f"    Narrative:  {BOLD}{trajectory.get('narrative', '?')}{RESET}")
        print(f"    Confidence: {trajectory.get('confidence', 0):.2f}")
        probs = trajectory.get("probabilities", {})
        print(f"    Probabilities:")
        for k, v in probs.items():
            color = GREEN if k == "deep_work" else RED if k == "fragmented" else YELLOW if k == "recovering" else DIM
            print(f"      {k:<12} {_render_bar(v)} {color}{v:.2f}{RESET}")
    else:
        print(f"    {DIM}(No trajectory data){RESET}")
    print()
    
    # 2. Presence Modulation Profile
    print(f"  {BOLD}{YELLOW}── BEHAVIORAL MODULATION ──{RESET}")
    if modulation:
        print(f"    Verbosity:     {BOLD}{modulation.get('verbosity')}{RESET}")
        print(f"    Cadence:       {BOLD}{modulation.get('cadence')}{RESET}")
        print(f"    Emotional Tone:{BOLD}{modulation.get('emotional_temperature')}{RESET}")
        print(f"    Interrupt Sens:{modulation.get('interruption_sensitivity'):.2f}")
        print(f"    Ambient Density:{modulation.get('ambient_density'):.2f}")
    else:
        print(f"    {DIM}(No modulation data){RESET}")
    print()
    
    # 3. Active Cognitive Signals
    print(f"  {BOLD}{GREEN}── ACTIVE COGNITIVE SIGNALS (Pressure) ──{RESET}")
    active = priority.get("active_signals", [])
    if active:
        for sig in sorted(active, key=lambda x: x["pressure"], reverse=True):
            pressure = sig["pressure"]
            color = RED if pressure > 0.8 else YELLOW if pressure > 0.4 else GREEN
            print(f"    {BOLD}{sig['type']}{RESET} [{sig['visibility']}]")
            print(f"      Pressure: {color}{_render_bar(pressure, 10)} {pressure:.2f}{RESET}  Conf: {sig['confidence']:.2f}  Nov: {sig['novelty']:.2f}  Recur: {sig['recurrence']}")
    else:
        print(f"    {DIM}(No active signals accumulating){RESET}")
    print()
    
    # 4. Suppressed Signals
    print(f"  {BOLD}{DIM}── RECENTLY SUPPRESSED SIGNALS ──{RESET}")
    suppressed = priority.get("suppressed_signals", [])
    if suppressed:
        for sig in suppressed[-5:]:
            print(f"    {DIM}{sig['type']} — Reason: {sig['reason']}{RESET}")
    else:
        print(f"    {DIM}(None){RESET}")
    print()
    
    print(f"  {DIM}Polled at {time.strftime('%H:%M:%S')}{RESET}")


async def main():
    watch = "--watch" in sys.argv
    if not os.path.exists(SOCKET_PATH):
        print(f"{RED}Error: Arova daemon not running (no socket at {SOCKET_PATH}){RESET}")
        sys.exit(1)
        
    if watch:
        while True:
            try:
                data = await query_cognition()
                render_snapshot(data)
            except Exception as e:
                print(f"{RED}Connection error: {e}{RESET}")
            await asyncio.sleep(POLL_INTERVAL)
    else:
        data = await query_cognition()
        render_snapshot(data)

if __name__ == "__main__":
    asyncio.run(main())
