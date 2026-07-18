from enum import Enum

class Capability(Enum):
    """
    Phase 6C capability taxonomy.
    These represent WHAT the system needs, not WHO provides it.
    The CapabilityRouter maps these to concrete providers via RoutingPolicy.
    """
    CHAT = "chat"
    REASONING = "reasoning"
    EMBEDDINGS = "embeddings"
    SUMMARIZATION = "summarization"
    VISION = "vision"
    
    # Phase 8: Expanded Cognitive Actions
    MEMORY_RECALL = "memory_recall"
    MEMORY_WRITE = "memory_write"
    TOOL_EXECUTION = "tool_execution"
    AGENT_LAUNCH = "agent_launch"
    SEARCH = "search"
    CONTINUITY_RESUME = "continuity_resume"
    NO_ACTION = "no_action"
