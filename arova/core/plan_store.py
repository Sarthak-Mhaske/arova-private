"""
plan_store.py — JSON-backed atomic persistence for HyprVoice plans.
"""

from __future__ import annotations

import json
import threading
import time
import os
from pathlib import Path
from typing import Any

_PLANS_FILE = Path.home() / ".cache" / "hyprvoice" / "plans.json"
_lock = threading.Lock()

def _load_raw() -> list[dict[str, Any]]:
    """Load raw plans list from disk. Returns [] on missing/corrupt file."""
    try:
        if _PLANS_FILE.exists():
            with open(_PLANS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except Exception:
        pass
    return []

def _save_raw(plans: list[dict[str, Any]]) -> None:
    """Persist plans list to disk atomically with fsync guarantee."""
    _PLANS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PLANS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(plans, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(_PLANS_FILE)

# ─── public API ───────────────────────────────────────────────────────────────

def get_plans() -> list[dict[str, Any]]:
    """Return all saved plans (newest first)."""
    with _lock:
        plans = _load_raw()
    return list(reversed(plans))

def get_plan(plan_id: str) -> dict[str, Any] | None:
    """Fetch a single plan by ID."""
    with _lock:
        for p in _load_raw():
            if p.get("id") == plan_id:
                return p
    return None

def save_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """
    Persist a fully validated plan to disk.
    Overwrites if the plan ID exists, otherwise appends.
    """
    with _lock:
        plans = _load_raw()
        for i, p in enumerate(plans):
            if p.get("id") == plan["id"]:
                plans[i] = plan
                _save_raw(plans)
                return plan
        plans.append(plan)
        _save_raw(plans)
    return plan

def delete_plan(plan_id: str) -> bool:
    """Remove a plan by ID. Returns True if deleted."""
    with _lock:
        plans = _load_raw()
        new_plans = [p for p in plans if p.get("id") != plan_id]
        if len(new_plans) == len(plans):
            return False
        _save_raw(new_plans)
    return True
