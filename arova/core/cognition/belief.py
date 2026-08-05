import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

@dataclass
class Hypothesis:
    title: str
    probability: float  # 0.0 - 1.0 posterior probability
    evidence_chain: List[str] = field(default_factory=list)
    evidence_weights: List[Dict[str, Any]] = field(default_factory=list)  # Inspectable weight deltas
    prior_memory_boost: float = 0.0  # Memory-informed prior boost (Continual Learning)
    created_at: float = field(default_factory=time.time)
    last_supported_at: float = field(default_factory=time.time)

@dataclass
class BeliefState:
    active_belief: Optional[Hypothesis] = None
    competing_hypotheses: List[Hypothesis] = field(default_factory=list)
    uncertainty_index: float = 0.5  # High when probabilities are close, low when dominant
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_belief": asdict(self.active_belief) if self.active_belief else None,
            "competing_hypotheses": [asdict(h) for h in self.competing_hypotheses],
            "uncertainty_index": round(self.uncertainty_index, 2),
            "updated_at": self.updated_at
        }

class BeliefRuntime:
    """
    Belief Runtime (`Cognitive OS Layer`).
    Maintains evolving, competing hypotheses about user intent with dynamic probability distributions.
    Allows Arova to model uncertainty and shift beliefs as new evidence accumulates.
    """
    def __init__(self, event_bus: Optional[Any] = None):
        self.event_bus = event_bus
        self.state = BeliefState()

    def update_evidence(self, working_memory_dict: Dict[str, Any]) -> BeliefState:
        """
        Evaluates working memory evidence, updates probability distribution across competing hypotheses,
        and emits BELIEF_SHIFTED if a competing hypothesis becomes dominant.
        """
        now = time.time()
        self.state.updated_at = now

        active_files = working_memory_dict.get("active_files", [])
        errors = working_memory_dict.get("unresolved_errors", [])
        terminal = working_memory_dict.get("terminal_evidence", [])
        browsers = working_memory_dict.get("browser_evidence", [])
        repo = working_memory_dict.get("current_repository", "workspace")

        hypotheses: List[Hypothesis] = []

        # Hypothesis 1: Terminal/Error Debugging
        failed_cmds = [t for t in terminal if t.get("exit_code") not in (None, 0)]
        if errors or failed_cmds:
            err_msg = errors[-1] if errors else failed_cmds[-1].get("command", "test run")
            weights = [
                {"weight": 0.40, "evidence": f"Failed command execution: {err_msg[:40]}"},
                {"weight": 0.32, "evidence": f"{len(errors)} unresolved diagnostic stacktraces"}
            ]
            raw_score = sum(w["weight"] for w in weights)
            hypotheses.append(Hypothesis(
                title=f"Eliminating error or test failure: {err_msg[:60]}",
                probability=raw_score,
                evidence_chain=[f"Error output: {err_msg[:50]}", f"{len(failed_cmds)} failed commands"],
                evidence_weights=weights
            ))

        # Hypothesis 2: Feature Development
        if active_files:
            top_file = active_files[-1].get("path", "").split("/")[-1]
            weights = [
                {"weight": 0.35, "evidence": f"Active file edit target: {top_file}"},
                {"weight": 0.15, "evidence": f"{len(active_files)} workspace active files"}
            ]
            raw_score = sum(w["weight"] for w in weights)
            hypotheses.append(Hypothesis(
                title=f"Implementing feature logic in {top_file}",
                probability=raw_score,
                evidence_chain=[f"Active edits in {top_file}", f"{len(active_files)} open files in workspace"],
                evidence_weights=weights
            ))

        # Hypothesis 3: Research / Documentation Reading
        if browsers:
            top_url = browsers[-1].get("title") or browsers[-1].get("url", "")
            weights = [
                {"weight": 0.35, "evidence": f"Documentation tab open: {top_url[:40]}"}
            ]
            raw_score = sum(w["weight"] for w in weights)
            hypotheses.append(Hypothesis(
                title=f"Researching documentation: {top_url[:50]}",
                probability=raw_score,
                evidence_chain=[f"Active tab: {top_url[:40]}"],
                evidence_weights=weights
            ))

        if not hypotheses:
            hypotheses.append(Hypothesis(
                title="Observing workspace activity",
                probability=0.20,
                evidence_chain=["Initial boot observation"],
                evidence_weights=[{"weight": 0.20, "evidence": "Baseline observation"}]
            ))

        # Normalize posterior probabilities so sum = 1.0
        total_score = sum(h.probability + h.prior_memory_boost for h in hypotheses)
        for h in hypotheses:
            h.probability = round((h.probability + h.prior_memory_boost) / total_score, 2)

        # Sort by probability descending
        hypotheses.sort(key=lambda h: h.probability, reverse=True)

        old_active_title = self.state.active_belief.title if self.state.active_belief else None
        self.state.active_belief = hypotheses[0]
        self.state.competing_hypotheses = hypotheses[1:]

        # Calculate uncertainty index (close top probabilities = high uncertainty)
        if len(hypotheses) > 1:
            diff = self.state.active_belief.probability - hypotheses[1].probability
            self.state.uncertainty_index = round(1.0 - diff, 2)
        else:
            self.state.uncertainty_index = 0.1

        # Emit BELIEF_SHIFTED if top hypothesis changed
        if old_active_title and old_active_title != self.state.active_belief.title:
            if self.event_bus:
                try:
                    self.event_bus.emit("cognition", "BELIEF_SHIFTED", self.state.to_dict())
                except Exception as e:
                    logger.debug(f"Failed to emit BELIEF_SHIFTED: {e}")

        return self.state

    def synthesize_objective_explanation(self) -> str:
        """
        Produces the human-grade objective answer to: 'What do you think I am trying to accomplish?'
        """
        if not self.state.active_belief:
            return "Observing workspace activity to infer active objective."

        active = self.state.active_belief
        explanation = f"Primary objective: {active.title} (Confidence: {int(active.probability * 100)}%).\n"
        if active.evidence_chain:
            evidence_str = ", ".join(active.evidence_chain)
            explanation += f"Supported by evidence: {evidence_str}.\n"

        if self.state.competing_hypotheses:
            alt = self.state.competing_hypotheses[0]
            explanation += f"Competing hypothesis ({int(alt.probability * 100)}%): {alt.title}."

        return explanation
