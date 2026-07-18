from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class IntentClassificationDTO:
    category: str
    confidence: float
    reasoning: str
    
@dataclass
class CognitiveStateDTO:
    state: str
    details: str
