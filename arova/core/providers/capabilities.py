from enum import Enum
from dataclasses import dataclass, field
from typing import Set

class Capability(Enum):
    """
    Capability taxonomy representing WHAT the system or task needs, not WHO provides it.
    The CapabilityRouter and ModelRegistry map these directly to concrete providers and models.
    """
    CHAT = "chat"
    REASONING = "reasoning"
    EMBEDDINGS = "embeddings"
    SUMMARIZATION = "summarization"
    VISION = "vision"
    CODING = "coding"
    IMAGE_GENERATION = "image_generation"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"
    TOOL_USE = "tool_use"
    
    # Expanded Cognitive Actions
    MEMORY_RECALL = "memory_recall"
    MEMORY_WRITE = "memory_write"
    TOOL_EXECUTION = "tool_execution"
    AGENT_LAUNCH = "agent_launch"
    SEARCH = "search"
    CONTINUITY_RESUME = "continuity_resume"
    NO_ACTION = "no_action"


@dataclass
class ProviderCapabilities:
    """
    Explicit feature transport capabilities advertised by each provider.
    Allows routing by requirement requirements (e.g. Vision + JSON Mode + Streaming) rather than provider names.
    """
    chat: bool = True
    reasoning: bool = False
    vision: bool = False
    embeddings: bool = False
    image_generation: bool = False
    speech_to_text: bool = False
    text_to_speech: bool = False
    function_calling: bool = False
    streaming: bool = True
    json_mode: bool = True
    tool_use: bool = False

    def to_set(self) -> Set[Capability]:
        caps = set()
        if self.chat: caps.add(Capability.CHAT)
        if self.reasoning: caps.add(Capability.REASONING)
        if self.vision: caps.add(Capability.VISION)
        if self.embeddings: caps.add(Capability.EMBEDDINGS)
        if self.image_generation: caps.add(Capability.IMAGE_GENERATION)
        if self.speech_to_text: caps.add(Capability.SPEECH_TO_TEXT)
        if self.text_to_speech: caps.add(Capability.TEXT_TO_SPEECH)
        if self.function_calling: caps.add(Capability.FUNCTION_CALLING)
        if self.streaming: caps.add(Capability.STREAMING)
        if self.json_mode: caps.add(Capability.JSON_MODE)
        if self.tool_use: caps.add(Capability.TOOL_USE)
        return caps
