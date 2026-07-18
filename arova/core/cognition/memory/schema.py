from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
import uuid

@dataclass
class MemoryMetadata:
    """
    Enforces rich metadata for all embeddings so Arova doesn't become a junk drawer.
    Supports intelligent decay and hybrid retrieval.
    """
    semantic_type: str                  # e.g., "intent", "transcript", "workspace_snapshot", "automation_trace"
    source_context: str                 # e.g., "vscode", "firefox", "voice_mic"
    confidence: float = 1.0             # 0.0 to 1.0 (how sure Arova is of this memory)
    attention_weight: float = 0.5       # 0.0 to 1.0 (derived from focus_depth at time of encoding)
    retrieval_frequency: int = 0        # How many times this memory has been successfully retrieved
    last_retrieved: Optional[float] = None # Timestamp of last retrieval for decay math
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "semantic_type": self.semantic_type,
            "source_context": self.source_context,
            "confidence": self.confidence,
            "attention_weight": self.attention_weight,
            "retrieval_frequency": self.retrieval_frequency,
            "last_retrieved": self.last_retrieved
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryMetadata':
        return cls(
            semantic_type=data.get("semantic_type", "unknown"),
            source_context=data.get("source_context", "unknown"),
            confidence=data.get("confidence", 1.0),
            attention_weight=data.get("attention_weight", 0.5),
            retrieval_frequency=data.get("retrieval_frequency", 0),
            last_retrieved=data.get("last_retrieved", None)
        )

@dataclass
class VectorMemory:
    """
    A single localized memory unit.
    """
    content: str
    metadata: MemoryMetadata
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
