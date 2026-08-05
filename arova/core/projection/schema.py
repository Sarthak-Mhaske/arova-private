from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class VisibleThread:
    thread_id: str
    title: str
    state: str # foreground, ambient, latent, archived
    pinned: bool = False
    last_active: float = 0.0
    continuity_resonance: float = 0.0
    workspace_match: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    unresolved_questions: List[str] = field(default_factory=list)
    why_it_matters: str = ""

@dataclass
class StreamItem:
    turn_id: str
    role: str
    content: str
    interrupted: bool = False

@dataclass
class RuntimeProjection:
    """
    The perceptual renderer payload. 
    This is the ONLY data the frontend receives.
    It strips away all internal cognition graphs, fatigue vectors, and raw intents.
    """
    orb_state: Dict[str, Any] = field(default_factory=dict)
    visible_threads: List[VisibleThread] = field(default_factory=list)
    ambient_fragments: List[str] = field(default_factory=list)
    stream_items: List[StreamItem] = field(default_factory=list)
    room_state: Dict[str, Any] = field(default_factory=dict)
    context_state: Dict[str, Any] = field(default_factory=dict)
    runtime_state: Dict[str, Any] = field(default_factory=dict)
    surfaces: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)
