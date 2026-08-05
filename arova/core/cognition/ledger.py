import time
import json
import logging
import hashlib
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class Evidence:
    trigger_signal: str
    context_keys: List[str]
    raw_data: Dict[str, Any]
    
    def fingerprint(self) -> str:
        """Create a deterministic fingerprint to enforce cooldowns on identical issues."""
        fingerprint_data = {
            "trigger": self.trigger_signal,
            "context": sorted(self.context_keys)
        }
        return hashlib.sha256(json.dumps(fingerprint_data, sort_keys=True).encode()).hexdigest()

@dataclass
class CompletedWork:
    title: str
    summary: str
    evidence: Evidence
    suggested_actions: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 1.0

@dataclass
class LedgerEntry:
    timestamp: float
    trigger: str
    need_score: float
    opportunity_score: float
    tool_route: str
    evidence_fingerprint: str
    outcome: str
    user_accepted: Optional[bool] = None

class InvestigationLedger:
    """
    Internal ledger for tracking proactive interventions. 
    Crucial for debugging, measuring false positives, and enforcing evidence-based cooldowns.
    """
    def __init__(self):
        self.entries: List[LedgerEntry] = []
        self.cooldown_duration = 1800  # 30 minutes
        
    def append_record(self, trigger: str, need_score: float, opp_score: float, route: str, evidence: Evidence, outcome: str):
        entry = LedgerEntry(
            timestamp=time.time(),
            trigger=trigger,
            need_score=need_score,
            opportunity_score=opp_score,
            tool_route=route,
            evidence_fingerprint=evidence.fingerprint(),
            outcome=outcome
        )
        self.entries.append(entry)
        logger.info(f"Ledger Recorded Investigation: {trigger} | Route: {route} | Outcome: {outcome}")
        
    def should_cooldown(self, evidence: Evidence) -> bool:
        """Check if we have already investigated this exact evidence recently."""
        fp = evidence.fingerprint()
        now = time.time()
        for entry in reversed(self.entries):
            if entry.evidence_fingerprint == fp:
                if (now - entry.timestamp) < self.cooldown_duration:
                    return True
                else:
                    return False
        return False
        
    def mark_user_feedback(self, evidence_fingerprint: str, accepted: bool):
        for entry in reversed(self.entries):
            if entry.evidence_fingerprint == evidence_fingerprint:
                entry.user_accepted = accepted
                break
