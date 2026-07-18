import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class RealityLayer:
    """
    Layer 1: Objective, deterministic facts gathered from providers, timeline, and focus telemetry.
    Zero-LLM dependency. Exists even if AI interpretation changes or fails.
    """
    resources: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    session_ids: List[str] = field(default_factory=list)
    memory_ids: List[str] = field(default_factory=list)
    timeline_event_ids: List[str] = field(default_factory=list)
    provider_fragments: List[Dict[str, Any]] = field(default_factory=list)
    total_focus_seconds: float = 0.0
    last_accessed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RealityLayer':
        return cls(**data)


@dataclass
class InterpretationLayer:
    """
    Layer 2: Deterministic heuristic & interpretation layer sitting between Reality and Understanding.
    Groups objective activity by shared repositories, domains, repeated terms, and universal stuckness telemetry.
    """
    repo_paths: List[str] = field(default_factory=list)
    browser_domains: List[str] = field(default_factory=list)
    repeated_terms: List[str] = field(default_factory=list)
    cluster_cohesion_score: float = 0.0
    stuckness_score: float = 0.0
    stuckness_reasons: List[str] = field(default_factory=list)
    last_extracted_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InterpretationLayer':
        return cls(**data)

# Backward compatibility alias
SignalsLayer = InterpretationLayer


@dataclass
class WorkspaceMomentum:
    goal: str = "Observing activity and forming workspace understanding..."
    progress_percentage: int = 0
    confidence_level: str = "Low"  # High | Medium | Low
    current_blocker: Optional[str] = None
    next_action: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkspaceMomentum':
        return cls(**data)


@dataclass
class WorkspaceHealth:
    status: str = "Exploring"  # Lifecycle: Exploring | Planning | Building | Blocked | Recovering | Shipping | Completed | Archived
    last_progress_reason: str = "Observing initial signals"
    last_progress_timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkspaceHealth':
        return cls(**data)


@dataclass
class WorkspaceConfidence:
    score: int = 20  # 0 to 100 percentage
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkspaceConfidence':
        return cls(**data)


@dataclass
class ItemConfidence:
    score: int = 85
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ItemConfidence':
        return cls(**data)


@dataclass
class ConfidenceLayer:
    """
    Layer 4: Granular certainty metrics per understanding conclusion.
    Ensures Arova behaves humbly ('I think you are implementing X' vs 'You are implementing X').
    """
    goal: ItemConfidence = field(default_factory=lambda: ItemConfidence(80, ["Observed consistent activity"]))
    blocker: ItemConfidence = field(default_factory=lambda: ItemConfidence(70, ["Heuristic error analysis"]))
    next_action: ItemConfidence = field(default_factory=lambda: ItemConfidence(75, ["Trajectory inference"]))
    overall: WorkspaceConfidence = field(default_factory=WorkspaceConfidence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal.to_dict(),
            "blocker": self.blocker.to_dict(),
            "next_action": self.next_action.to_dict(),
            "overall": self.overall.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfidenceLayer':
        obj = cls()
        if "goal" in data:
            obj.goal = ItemConfidence.from_dict(data["goal"])
        if "blocker" in data:
            obj.blocker = ItemConfidence.from_dict(data["blocker"])
        if "next_action" in data:
            obj.next_action = ItemConfidence.from_dict(data["next_action"])
        if "overall" in data:
            obj.overall = WorkspaceConfidence.from_dict(data["overall"])
        return obj


@dataclass
class UnderstandingLayer:
    """
    Layer 3: Deep AI interpretation and synthesis of Reality and Interpretation layers.
    Maintains living momentum, health, confidence, decisions, questions, and delta changes.
    """
    momentum: WorkspaceMomentum = field(default_factory=WorkspaceMomentum)
    health: WorkspaceHealth = field(default_factory=WorkspaceHealth)
    confidence: WorkspaceConfidence = field(default_factory=WorkspaceConfidence)
    confidence_layer: ConfidenceLayer = field(default_factory=ConfidenceLayer)
    decisions: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    state_summary: str = "Active trajectory progression"
    what_changed: str = "Initial workspace observations established."
    trajectory_story: str = "Trajectory is developing through steady focus and activity."
    last_synthesized_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["momentum"] = self.momentum.to_dict()
        d["health"] = self.health.to_dict()
        d["confidence"] = self.confidence.to_dict()
        d["confidence_layer"] = self.confidence_layer.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnderstandingLayer':
        momentum_data = data.pop("momentum", {})
        health_data = data.pop("health", {})
        confidence_data = data.pop("confidence", {})
        confidence_layer_data = data.pop("confidence_layer", {})
        
        obj = cls(**data)
        if isinstance(momentum_data, dict):
            obj.momentum = WorkspaceMomentum.from_dict(momentum_data)
        elif isinstance(momentum_data, WorkspaceMomentum):
            obj.momentum = momentum_data

        if isinstance(health_data, dict):
            obj.health = WorkspaceHealth.from_dict(health_data)
        elif isinstance(health_data, WorkspaceHealth):
            obj.health = health_data

        if isinstance(confidence_data, dict):
            obj.confidence = WorkspaceConfidence.from_dict(confidence_data)
        elif isinstance(confidence_data, WorkspaceConfidence):
            obj.confidence = confidence_data

        if isinstance(confidence_layer_data, dict) and confidence_layer_data:
            obj.confidence_layer = ConfidenceLayer.from_dict(confidence_layer_data)
        elif isinstance(confidence_layer_data, ConfidenceLayer):
            obj.confidence_layer = confidence_layer_data

        return obj


@dataclass
class CognitiveWorkspace:
    """
    Root domain model for long-lived ongoing work (e.g., 'Arova Development', '2026 Tax Return').
    Emits no database jargon to the user; acts as a living mind tracking progress, context, and trajectory.
    """
    workspace_id: str = field(default_factory=lambda: f"ws_{uuid.uuid4().hex[:12]}")
    title: str = "New Workspace"
    domain_type: str = "general"  # engineering | finance | law | research | general
    pinned: bool = False
    created_at: float = field(default_factory=time.time)

    reality: RealityLayer = field(default_factory=RealityLayer)
    interpretation: InterpretationLayer = field(default_factory=InterpretationLayer)
    understanding: UnderstandingLayer = field(default_factory=UnderstandingLayer)

    @property
    def signals(self) -> InterpretationLayer:
        """Backward-compatibility alias during schema transition."""
        return self.interpretation

    @signals.setter
    def signals(self, value: InterpretationLayer):
        self.interpretation = value

    def get_seven_questions(self) -> Dict[str, str]:
        """
        Returns natural language answers to the Seven Fundamental Questions as views over the deep model.
        Follows the Golden Rule: 'A Workspace should feel like a mind, not a database.'
        """
        u = self.understanding
        m = u.momentum
        c = u.confidence
        cl = u.confidence_layer
        
        # 1. What am I doing?
        what = self.title if self.title != "New Workspace" else "Exploring a new task"
        
        # 2. Why am I doing it?
        why = m.goal
        if cl.goal.score < 85 and c.score < 85:
            why = f"I think the goal is: {why} (Confidence: {cl.goal.score}%)"
            
        # 3. How far am I?
        how_far = f"You are around {m.progress_percentage}% along. Health status: {u.health.status}."
        
        # 4. What's blocking me?
        blocker = m.current_blocker if m.current_blocker else "No critical blockers right now."
        if m.current_blocker and cl.blocker.score < 85 and c.score < 85:
            blocker = f"Possible blocker: {blocker} ({cl.blocker.score}% certainty)"
            
        # 5. What should I do next?
        next_do = m.next_action if m.next_action else "Continue observing current signals."
        if m.next_action and cl.next_action.score < 85 and c.score < 85:
            next_do = f"Suggested focus: {next_do} ({cl.next_action.score}% certainty)"
            
        # 6. Why do you believe that?
        reasons_text = ", ".join(c.reasons) if c.reasons else "Initial observations."
        why_believe = f"Confidence is {c.score}% based on: {reasons_text}."

        # 7. What changed?
        changed = u.what_changed if u.what_changed else "Progressing along defined milestones."

        return {
            "what_am_i_doing": what,
            "why_am_i_doing_it": why,
            "how_far_am_i": how_far,
            "whats_blocking_me": blocker,
            "what_should_i_do_next": next_do,
            "why_do_you_believe_that": why_believe,
            "what_changed": changed
        }

    def get_six_questions(self) -> Dict[str, str]:
        """Backward compatibility alias for the six questions view."""
        q = self.get_seven_questions()
        return {
            "what_am_i_doing": q["what_am_i_doing"],
            "why_am_i_doing_it": q["why_am_i_doing_it"],
            "how_far_am_i": q["how_far_am_i"],
            "whats_blocking_me": q["whats_blocking_me"],
            "what_should_i_do_next": q["what_should_i_do_next"],
            "why_do_you_believe_that": q["why_do_you_believe_that"]
        }

    def get_trajectory_story(self) -> Dict[str, Any]:
        """Returns the Yesterday -> Today trajectory story for human-centric understanding."""
        u = self.understanding
        m = u.momentum
        return {
            "title": self.title,
            "goal": m.goal,
            "progress_story": f"{m.progress_percentage}% complete",
            "what_changed": u.what_changed,
            "trajectory_story": u.trajectory_story,
            "decisions": u.decisions,
            "blocker_status": m.current_blocker if m.current_blocker else "Resolved / None",
            "next_action": m.next_action
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "title": self.title,
            "domain_type": self.domain_type,
            "pinned": self.pinned,
            "created_at": self.created_at,
            "reality": self.reality.to_dict(),
            "interpretation": self.interpretation.to_dict(),
            "signals": self.interpretation.to_dict(),  # backward compatibility
            "understanding": self.understanding.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CognitiveWorkspace':
        data = dict(data)  # shallow copy
        reality_data = data.pop("reality", {})
        interpretation_data = data.pop("interpretation", {}) or data.pop("signals", {})
        data.pop("signals", None)  # clean remaining if any
        understanding_data = data.pop("understanding", {})

        ws = cls(**data)
        if isinstance(reality_data, dict):
            ws.reality = RealityLayer.from_dict(reality_data)
        elif isinstance(reality_data, RealityLayer):
            ws.reality = reality_data

        if isinstance(interpretation_data, dict):
            ws.interpretation = InterpretationLayer.from_dict(interpretation_data)
        elif isinstance(interpretation_data, InterpretationLayer):
            ws.interpretation = interpretation_data

        if isinstance(understanding_data, dict):
            ws.understanding = UnderstandingLayer.from_dict(understanding_data)
        elif isinstance(understanding_data, UnderstandingLayer):
            ws.understanding = understanding_data

        return ws
