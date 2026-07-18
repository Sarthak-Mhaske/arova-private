from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class ProvenanceSource:
    source_type: str # e.g., 'workspace', 'file', 'memory', 'timeline'
    source_id: str   # e.g., 'VSCode', 'memory_policy.py', 'event_123'
    confidence: float # 0.0 to 1.0
    explanation: str # Human-readable reason, e.g., 'Focused for 45 minutes'
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "confidence": self.confidence,
            "explanation": self.explanation
        }
