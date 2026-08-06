import sys
import logging
from arova.core.cognition.ledger import InvestigationLedger
from arova.core.cognition.investigator import ProactiveInvestigator

logging.basicConfig(level=logging.INFO, format="%(message)s")

def main():
    ledger = InvestigationLedger()
    investigator = ProactiveInvestigator(ledger)
    
    print("\n--- TEST 1: True Positive (Pytest Failure) ---")
    telemetry_fail = {
        "active_app": "code",
        "window_title": "pytest failure in storage.py",
        "terminal_consecutive_failures": 3,
        "terminal_last_output": "AssertionError",
        "idle_seconds": 25
    }
    work1 = investigator.evaluate_and_investigate(telemetry_fail)
    if work1:
        print(f"[SUCCESS] Intervention triggered. Route: {work1.summary}")
    else:
        print("[FAIL] Intervention should have triggered.")
        
    print("\n--- TEST 2: True Positive (Cooldown Check) ---")
    work2 = investigator.evaluate_and_investigate(telemetry_fail)
    if not work2:
        print("[SUCCESS] Cooldown enforced. No intervention triggered.")
    else:
        print("[FAIL] Cooldown was ignored!")
        
    print("\n--- TEST 3: True Positive (Vision Fallback on Figma) ---")
    telemetry_figma = {
        "active_app": "figma",
        "window_title": "Design System",
        "app_not_responding": True,
        "idle_seconds": 60
    }
    work3 = investigator.evaluate_and_investigate(telemetry_figma)
    if work3:
        print(f"[SUCCESS] Intervention triggered. Route: {work3.summary}")
    else:
        print("[FAIL] Intervention should have triggered.")

    print("\n--- TEST 4: False Positive (Watching YouTube) ---")
    telemetry_yt = {
        "active_app": "chrome",
        "window_title": "Funny Cats - YouTube",
        "idle_seconds": 300,
        "terminal_consecutive_failures": 0
    }
    work4 = investigator.evaluate_and_investigate(telemetry_yt)
    if not work4:
        print("[SUCCESS] False positive avoided on YouTube.")
    else:
        print("[FAIL] Intervention triggered on YouTube!")
        
    print("\n--- TEST 5: False Positive (Reading Docs) ---")
    telemetry_docs = {
        "active_app": "chrome",
        "window_title": "SQLite WAL Documentation",
        "idle_seconds": 60,
        "terminal_consecutive_failures": 0
    }
    work5 = investigator.evaluate_and_investigate(telemetry_docs)
    if not work5:
        print("[SUCCESS] False positive avoided on reading docs.")
    else:
        print("[FAIL] Intervention triggered while reading docs!")
        
    print("\n--- LEDGER VERIFICATION ---")
    print(f"Total Ledger Entries: {len(ledger.entries)}")
    for i, entry in enumerate(ledger.entries):
        print(f"  Entry {i+1}: Route={entry.tool_route}, Need={entry.need_score:.2f}, Opp={entry.opportunity_score:.2f}, Outcome={entry.outcome}")

if __name__ == "__main__":
    main()
