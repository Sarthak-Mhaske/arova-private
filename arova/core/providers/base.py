import abc
import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, AsyncGenerator, Set
from arova.core.providers.capabilities import Capability

logger = logging.getLogger(__name__)


@dataclass
class ProviderHealth:
    """
    Live health telemetry for a provider.
    The CapabilityRouter uses this to prefer healthy providers
    and to detect when a dead provider recovers.
    """
    available: bool = True
    latency_ms: float = 0.0
    success_rate: float = 1.0
    last_failure: float = 0.0       # epoch timestamp
    last_success: float = 0.0       # epoch timestamp
    consecutive_failures: int = 0

    def record_success(self, latency_ms: float):
        self.available = True
        self.latency_ms = latency_ms
        self.last_success = time.time()
        self.consecutive_failures = 0
        # Exponential moving average for success rate
        self.success_rate = min(1.0, self.success_rate * 0.9 + 0.1)

    def record_failure(self):
        self.last_failure = time.time()
        self.consecutive_failures += 1
        self.success_rate = max(0.0, self.success_rate * 0.8)
        if self.consecutive_failures >= 3:
            self.available = False

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "latency_ms": round(self.latency_ms, 1),
            "success_rate": round(self.success_rate, 3),
            "consecutive_failures": self.consecutive_failures
        }


class CognitiveProvider(abc.ABC):
    """
    Abstract base for all inference providers.
    Each provider declares which Capabilities it supports.
    The CapabilityRouter never calls a provider for a capability it doesn't declare.
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
