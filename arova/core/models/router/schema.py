from dataclasses import dataclass, field
from arova.core.providers.capabilities import Capability
from typing import Dict

@dataclass
class CapabilityVector:
    """
    A probability vector determining the likelihood of each capability
    being the optimal action for a given CognitiveSituation.
    """
    chat: float = 0.0
    reasoning: float = 0.0
    memory_recall: float = 0.0
    memory_write: float = 0.0
    tool_execution: float = 0.0
    agent_launch: float = 0.0
    vision: float = 0.0
    search: float = 0.0
    continuity_resume: float = 0.0
    no_action: float = 0.0
    
    # Measure of ambiguity. Calculated as the delta between the top two capabilities.
    # A confidence < 0.65 indicates ambiguity, requiring an AmbiguityRouterLLM.
    confidence: float = 1.0

    def get_top_capability(self) -> Capability:
        scores = {
            Capability.CHAT: self.chat,
            Capability.REASONING: self.reasoning,
            Capability.MEMORY_RECALL: self.memory_recall,
            Capability.MEMORY_WRITE: self.memory_write,
            Capability.TOOL_EXECUTION: self.tool_execution,
            Capability.AGENT_LAUNCH: self.agent_launch,
            Capability.VISION: self.vision,
            Capability.SEARCH: self.search,
            Capability.CONTINUITY_RESUME: self.continuity_resume,
            Capability.NO_ACTION: self.no_action
        }
        return max(scores.items(), key=lambda x: x[1])[0]

    def recalculate_confidence(self):
        """Updates confidence based on the delta between top two scores."""
        scores = [
            self.chat, self.reasoning, self.memory_recall, self.memory_write,
            self.tool_execution, self.agent_launch, self.vision, self.search,
            self.continuity_resume, self.no_action
        ]
        sorted_scores = sorted(scores, reverse=True)
        if len(sorted_scores) >= 2:
            top, second = sorted_scores[0], sorted_scores[1]
            if top == 0:
                self.confidence = 0.0
            else:
                self.confidence = top - second
        else:
            self.confidence = 1.0
