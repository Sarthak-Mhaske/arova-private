import uuid
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Awaitable, Callable
from enum import Enum
from arova.core.events import EventPayload

class PolicyVerdict(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"

@dataclass
class PolicyEvaluation:
    verdict: PolicyVerdict
    reason: Optional[str] = None
    
@dataclass
class ApprovalRequest:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requester: str = "unknown"
    action: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    timeout_seconds: float = 30.0

class Policy(object):
    """Abstract base class for all governance rules."""
    async def evaluate(self, payload: EventPayload) -> PolicyEvaluation:
        return PolicyEvaluation(PolicyVerdict.ALLOW)

@dataclass
class PolicyChain:
    """A composable chain of policies that short-circuits on DENY or REQUIRE_APPROVAL."""
    name: str
    policies: List[Policy] = field(default_factory=list)
    
    async def evaluate_all(self, payload: EventPayload) -> PolicyEvaluation:
        for p in self.policies:
            res = await p.evaluate(payload)
            if res.verdict != PolicyVerdict.ALLOW:
                return res
        return PolicyEvaluation(PolicyVerdict.ALLOW)
