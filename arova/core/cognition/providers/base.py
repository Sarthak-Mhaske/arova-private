from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from enum import Enum
from arova.core.cognition.provenance import ProvenanceSource

class ProviderCapability(Enum):
    PRESENCE = "presence"
    CONTEXT = "context"
    DEEP_CONTEXT = "deep_context"
    VISION = "vision"

@dataclass
class ContextFragment:
    provider_id: str
    activity_summary: str
    source_identity: str
    confidence: float
    importance: float
    expires_at: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    provenance: List[ProvenanceSource] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "activity_summary": self.activity_summary,
            "source_identity": self.source_identity,
            "confidence": self.confidence,
            "importance": self.importance,
            "expires_at": self.expires_at,
            "tags": self.tags,
            "provenance": [p.to_dict() for p in self.provenance],
            "metadata": self.metadata
        }

class ContextProvider(ABC):
    capability: ProviderCapability
    
    @abstractmethod
    def get_id(self) -> str:
        """Returns the unique string identifier of this provider."""
        pass
        
    @abstractmethod
    def get_name(self) -> str:
        """Returns the human-readable name of this provider."""
        pass

    @abstractmethod
    async def detect(self) -> bool:
        """Returns True if the provider has active context to report."""
        pass
        
    @abstractmethod
    async def summarize(self) -> ContextFragment:
        """Returns the current cognitive activity and its source."""
        pass
