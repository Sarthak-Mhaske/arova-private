from arova.core.cognition.situation import CognitiveSituation
from arova.core.models.router.schema import CapabilityVector
import re

class CognitiveScorer:
    """
    Layers 1 & 2: Environment Weighting & Heuristic Scoring.
    Evaluates a CognitiveSituation and returns a CapabilityVector without using an LLM.
    """
    
    @classmethod
    def evaluate(cls, situation: CognitiveSituation) -> CapabilityVector:
        vector = CapabilityVector()
        
        # ---------------------------------------------------------
        # Layer 1: Environment Weighting
        # ---------------------------------------------------------
        
        # Room / Attention analysis
        if situation.attention_state == "deep_work":
            vector.reasoning += 0.3
            vector.tool_execution += 0.1
            
        if "VSCode" in situation.workspace or "Terminal" in situation.workspace:
            vector.reasoning += 0.4
            vector.tool_execution += 0.2
            
        if situation.room == "implementation":
            vector.reasoning += 0.2
            vector.tool_execution += 0.1
            
        # Continuity pressure
        if situation.continuity_pressure > 0.8:
            vector.continuity_resume += 0.5
            
        # ---------------------------------------------------------
        # Layer 2: Heuristic Complexity
        # ---------------------------------------------------------
        prompt = situation.prompt.lower().strip()
        
        # Chat heuristics (Simple greetings, thanks)
        if prompt in ["hello", "hi", "hey", "thanks", "thank you", "ok", "okay"]:
            vector.chat += 0.9
            vector.no_action += 0.1
            
        # Continuity explicit command
        if "continue where we left off" in prompt or "resume" in prompt:
            vector.continuity_resume += 0.95
            
        # Reasoning / Coding heuristics
        reasoning_keywords = ["design", "architecture", "analyze", "compare", "build", "write code", "explain"]
        if any(kw in prompt for kw in reasoning_keywords):
            vector.reasoning += 0.6
            
        # Code block detection
        if "```" in prompt:
            vector.reasoning += 0.5
            
        # Memory heuristics
        memory_keywords = ["do you remember", "what did we discuss", "recall", "search memory"]
        if any(kw in prompt for kw in memory_keywords):
            vector.memory_recall += 0.7
            
        # Tool heuristics
        tool_keywords = ["open settings", "switch thread", "show memory"]
        if any(kw in prompt for kw in tool_keywords):
            vector.tool_execution += 0.8
            
        # Vision heuristics
        if len(situation.attachments) > 0:
            # Check if image attachments exist
            if any(att.get("type", "").startswith("image") for att in situation.attachments):
                vector.vision += 0.9
                
        # Length heuristics (Long prompts often require more reasoning or memory reading)
        if len(prompt) > 500:
            vector.reasoning += 0.3
            
        # Question count
        if prompt.count("?") > 2:
            vector.reasoning += 0.2
            vector.chat += 0.1

        # Calculate ambiguity / confidence
        vector.recalculate_confidence()
        
        return vector
