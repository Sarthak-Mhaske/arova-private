import abc
from typing import List, Dict, Any, AsyncGenerator
from arova.core.models.trust import TrustZone

class ModelAdapter(abc.ABC):
    """
    Abstract base class for inference providers.
    """
    @property
    @abc.abstractmethod
    def trust_zone(self) -> TrustZone:
        pass
        
    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        pass

    @abc.abstractmethod
    async def invoke_structured(self, messages: List[Dict[str, Any]], system_prompt: str, model_name: str, max_tokens: int) -> Dict[str, Any]:
        """Returns parsed JSON."""
        pass

    @abc.abstractmethod
    async def invoke_stream(self, messages: List[Dict[str, Any]], system_prompt: str, model_name: str, max_tokens: int) -> AsyncGenerator[str, None]:
        """Yields chunks of text."""
        pass
        # Because we need async generators to use yield, we do it in concrete implementations.
