import abc
import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, AsyncGenerator, Set
from arova.core.providers.capabilities import Capability

logger = logging.getLogger(__name__)


@dataclass
class ProviderProfile:
    """
    Rich metadata describing a transport's recommended use cases without hardcoding UI logic.
    Onboarding UI queries transports by tags (e.g. tags=["coding"] or tags=["fast"]).
    """
    id: str
    name: str
    tags: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class SelectionExplanation:
    """
    Exposes exactly WHY the Policy chose a transport and candidate model for a given task.
    Enables rich debugging and data-driven routing analytics during beta and personalization.
    """
    capability_score: float = 1.0
    latency_score: float = 1.0
    availability_score: float = 1.0
    cost_score: float = 1.0
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "capability_score": round(self.capability_score, 2),
            "latency_score": round(self.latency_score, 2),
            "availability_score": round(self.availability_score, 2),
            "cost_score": round(self.cost_score, 2),
            "reasoning": self.reasoning
        }


@dataclass
class ProviderHealth:
    """
    Live health and multi-factor reliability telemetry for a provider.
    The CapabilityRouter uses this to score and prefer reliable transports.
    """
    available: bool = True
    status: str = "ok"              # e.g. "ok", "degraded", "401 Invalid key", "unreachable"
    latency_ms: float = 0.0
    success_rate: float = 1.0
    total_calls: int = 0
    total_failures: int = 0
    last_failure: float = 0.0       # epoch timestamp
    last_success: float = 0.0       # epoch timestamp
    consecutive_failures: int = 0
    last_error: str = ""
    rate_limited_until: float = 0.0

    @property
    def is_available(self) -> bool:
        return self.available and time.time() > self.rate_limited_until

    @property
    def availability_pct(self) -> float:
        if self.total_calls == 0:
            return 100.0 if self.available else 0.0
        return round(((self.total_calls - self.total_failures) / max(1, self.total_calls)) * 100.0, 1)

    def record_success(self, latency_ms: float):
        self.total_calls += 1
        self.available = True
        self.status = "ok"
        self.latency_ms = latency_ms
        self.last_success = time.time()
        self.consecutive_failures = 0
        self.last_error = ""
        # Exponential moving average for success rate
        self.success_rate = min(1.0, self.success_rate * 0.9 + 0.1)

    def record_failure(self, reason: str = ""):
        self.total_calls += 1
        self.total_failures += 1
        self.last_failure = time.time()
        self.consecutive_failures += 1
        self.success_rate = max(0.0, self.success_rate * 0.8)
        self.last_error = reason

        reason_lower = reason.lower()
        is_auth_error = "401" in reason or "invalid" in reason_lower
        is_rate_limit = "429" in reason or "rate limit" in reason_lower or "too many requests" in reason_lower

        if self.consecutive_failures >= 3 or is_auth_error:
            self.available = False
            self.status = reason if reason else "unreachable"

        if is_rate_limit:
            self.rate_limited_until = time.time() + 300
            self.status = "Rate Limited"

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "status": self.status,
            "availability_pct": self.availability_pct,
            "latency_ms": round(self.latency_ms, 1),
            "failures": f"{self.total_failures} / {max(1, self.total_calls)}",
            "success_rate": round(self.success_rate, 3),
            "consecutive_failures": self.consecutive_failures,
            "last_error": self.last_error
        }


class CognitiveProvider(abc.ABC):
    """
    Abstract base for all inference providers.
    Each provider advertises exact feature transport capabilities (ProviderCapabilities).
    The CapabilityRouter routes by requested capabilities requirements rather than provider names.
    """

    def __init__(self):
        self.health = ProviderHealth()

    # ---- Identity ----

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable provider name, e.g. 'groq', 'ollama'."""
        ...

    @property
    @abc.abstractmethod
    def supported_capabilities(self) -> Set[Capability]:
        """Return the set of capabilities this provider can fulfill."""
        ...

    @property
    def profile(self) -> ProviderProfile:
        """
        Recommended setup profile and tags for UI query resolution.
        """
        tags_map = {
            "anthropic": ["coding", "reasoning", "high_quality"],
            "groq": ["fast", "cheap", "instant"],
            "ollama": ["local", "private", "zero_key"],
            "lmstudio": ["local", "developer", "zero_key"],
            "openai": ["general", "reliable", "reasoning"],
            "gemini": ["long_context", "free_tier", "vision"],
            "openrouter": ["meta", "multi_model", "flexible"]
        }
        return ProviderProfile(
            id=self.name,
            name=self.name.capitalize(),
            tags=tags_map.get(self.name, ["general"]),
            description=f"{self.name.capitalize()} cognitive transport"
        )

    @property
    def advertised_capabilities(self) -> "ProviderCapabilities":
        """
        Rich capability flags advertised by this transport.
        Defaults to deriving from supported_capabilities if not explicitly overridden.
        """
        from arova.core.providers.capabilities import ProviderCapabilities
        caps = self.supported_capabilities
        return ProviderCapabilities(
            chat=Capability.CHAT in caps or Capability.FAST_CHAT in caps if hasattr(Capability, 'FAST_CHAT') else Capability.CHAT in caps,
            reasoning=Capability.REASONING in caps,
            vision=Capability.VISION in caps,
            embeddings=Capability.EMBEDDINGS in caps,
            image_generation=Capability.IMAGE_GENERATION in caps,
            speech_to_text=Capability.SPEECH_TO_TEXT in caps,
            text_to_speech=Capability.TEXT_TO_SPEECH in caps,
            function_calling=Capability.FUNCTION_CALLING in caps or Capability.TOOL_USE in caps,
            streaming=Capability.STREAMING in caps or True,
            json_mode=Capability.JSON_MODE in caps or True,
            tool_use=Capability.TOOL_USE in caps
        )

    # ---- Inference ----

    @abc.abstractmethod
    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       model: str, max_tokens: int) -> str:
        """Non-streaming text generation. Returns full response string."""
        ...

    @abc.abstractmethod
    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str, max_tokens: int) -> AsyncGenerator[str, None]:
        """Streaming text generation. Yields sentence-level chunks."""
        ...

    async def embed(self, text: str) -> List[float]:
        """Generate embeddings. Not all providers support this."""
        raise NotImplementedError(f"{self.name} does not support embeddings")

    # ---- Health ----

    async def health_check(self) -> ProviderHealth:
        """
        Actively probe the provider.
        Subclasses can override for provider-specific checks (e.g. Ollama HTTP ping).
        Default implementation just returns current health telemetry.
        """
        return self.health
