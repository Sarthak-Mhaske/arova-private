import os
import json
import time
import logging
import asyncio
import aiohttp
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

REGISTRY_VERSION = "v2026.07.19"


class ArovaCapability(Enum):
    """
    Arova-owned capability abstraction vocabulary.
    Providers map their discovered models onto these exact capabilities.
    """
    AROVA_CAPABILITY_FAST_CHAT = "fast_chat"
    AROVA_CAPABILITY_REASONING = "reasoning"
    AROVA_CAPABILITY_CODING = "coding"
    AROVA_CAPABILITY_RESUME_WORKSPACE = "resume_workspace"
    AROVA_CAPABILITY_SUMMARIZE = "summarize"
    AROVA_CAPABILITY_AMBIGUITY_ROUTING = "ambiguity_routing"
    AROVA_CAPABILITY_SCREEN_CONTEXT = "screen_context"
    AROVA_CAPABILITY_VISION = "vision"
    AROVA_CAPABILITY_EMBEDDING = "embedding"


class QualityTier(Enum):
    """
    Quality vs Cost/Speed tradeoffs requested by cognitive subsystems.
    """
    CHEAP = "cheap"
    BALANCED = "balanced"
    PREMIUM = "premium"


@dataclass
class ModelCandidate:
    """
    Rich model representation returned to requesting services.
    Includes exact capabilities, limits, and the explicit selection reason ("Why?").
    """
    id: str
    provider: str
    context_window: int
    supports_tools: bool
    supports_images: bool
    supports_reasoning: bool
    supports_json: bool
    latency_ms: int
    cost_per_1k_tokens: float
    health: str = "healthy"
    selection_reason: List[str] = field(default_factory=list)
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "provider": self.provider,
            "context_window": self.context_window,
            "supports_tools": self.supports_tools,
            "supports_images": self.supports_images,
            "supports_reasoning": self.supports_reasoning,
            "supports_json": self.supports_json,
            "latency_ms": self.latency_ms,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
            "health": self.health,
            "selection_reason": self.selection_reason,
            "score": round(self.score, 2)
        }


@dataclass
class ProviderManifest:
    """
    Base capability and limits manifest declared by each provider.
    """
    provider: str
    supported_capabilities: Set[ArovaCapability]
    limits: Dict[str, Any]


class CandidateScorer:
    """
    Composable policy scoring engine.
    Computes candidate scores from weighted capabilities without arbitrary static opinions.
    """
    @classmethod
    def score_candidate(cls, candidate: ModelCandidate, capability: ArovaCapability, quality: QualityTier) -> float:
        # Base capability compatibility check
        score = 50.0
        reasons = []

        # 1. Capability affinity scoring
        if capability in (ArovaCapability.AROVA_CAPABILITY_REASONING, ArovaCapability.AROVA_CAPABILITY_AMBIGUITY_ROUTING):
            if candidate.supports_reasoning or "qwen" in candidate.id.lower() or "deepseek" in candidate.id.lower() or "r1" in candidate.id.lower() or "gpt-4" in candidate.id.lower() or "gpt-5" in candidate.id.lower() or "o1" in candidate.id.lower() or "o3" in candidate.id.lower():
                score += 35.0
                reasons.append("Optimized for deep reasoning / complex inference")
            if candidate.supports_json:
                score += 15.0
                reasons.append("Guaranteed JSON structured output")
        elif capability == ArovaCapability.AROVA_CAPABILITY_CODING:
            if "qwen" in candidate.id.lower() or "coder" in candidate.id.lower() or "deepseek" in candidate.id.lower() or "kimi" in candidate.id.lower() or "claude" in candidate.id.lower() or "gpt" in candidate.id.lower():
                score += 40.0
                reasons.append("Strong coding and AST comprehension metrics")
            if candidate.supports_tools:
                score += 10.0
                reasons.append("Supports tool execution")
        elif capability in (ArovaCapability.AROVA_CAPABILITY_FAST_CHAT, ArovaCapability.AROVA_CAPABILITY_SUMMARIZE):
            if candidate.latency_ms <= 500:
                score += 30.0
                reasons.append(f"Ultra-fast response latency (~{candidate.latency_ms}ms)")
            if "70b" in candidate.id.lower() or "instant" in candidate.id.lower() or "mini" in candidate.id.lower() or "llama-3" in candidate.id.lower():
                score += 20.0
                reasons.append("High throughput conversational engine")
        elif capability == ArovaCapability.AROVA_CAPABILITY_VISION:
            if candidate.supports_images or "vision" in candidate.id.lower() or "vl" in candidate.id.lower() or "4o" in candidate.id.lower():
                score += 50.0
                reasons.append("Natively supports visual inspection")
            else:
                score = 0.0  # Cannot satisfy vision if no image support
        elif capability == ArovaCapability.AROVA_CAPABILITY_RESUME_WORKSPACE:
            if candidate.context_window >= 32768:
                score += 30.0
                reasons.append(f"Large context window ({candidate.context_window} tokens)")
            if candidate.supports_json:
                score += 20.0
                reasons.append("Precise structured state reconstruction")

        # 2. Quality Tier adjustment
        if quality == QualityTier.CHEAP:
            if candidate.cost_per_1k_tokens == 0.0:
                score += 25.0
                reasons.append("Zero cost (Local Edge execution)")
            elif candidate.cost_per_1k_tokens < 0.1:
                score += 15.0
                reasons.append("Low cost profile")
            else:
                score -= 20.0
        elif quality == QualityTier.PREMIUM:
            if candidate.context_window >= 65536 or candidate.supports_reasoning:
                score += 25.0
                reasons.append("Premium depth and reasoning fidelity")

        # 3. Health & Latency adjustments
        if candidate.health != "healthy":
            score -= 60.0
            reasons.append(f"Health degraded ({candidate.health})")
        if candidate.latency_ms > 2000 and quality != QualityTier.PREMIUM:
            score -= 15.0

        candidate.score = max(0.0, score)
        if reasons:
            candidate.selection_reason = reasons
        return candidate.score


class ModelRegistry:
    """
    Central Capability Registry and Live Catalog Manager.
    All components across Arova request ModelCandidate objects from this registry.
    """
    def __init__(self):
        self.version = REGISTRY_VERSION
        self.cache_path = os.path.expanduser("~/.arova/runtime/model_catalog_cache.json")
        self._candidates: Dict[str, List[ModelCandidate]] = {
            "groq": [],
            "openai": [],
            "ollama": [],
            "anthropic": [],
            "gemini": [],
            "openrouter": []
        }
        self._manifests: Dict[str, ProviderManifest] = {
            "groq": ProviderManifest(
                provider="groq",
                supported_capabilities={
                    ArovaCapability.AROVA_CAPABILITY_FAST_CHAT,
                    ArovaCapability.AROVA_CAPABILITY_REASONING,
                    ArovaCapability.AROVA_CAPABILITY_CODING,
                    ArovaCapability.AROVA_CAPABILITY_RESUME_WORKSPACE,
                    ArovaCapability.AROVA_CAPABILITY_SUMMARIZE,
                    ArovaCapability.AROVA_CAPABILITY_AMBIGUITY_ROUTING,
                    ArovaCapability.AROVA_CAPABILITY_VISION
                },
                limits={"context": 131072, "images": True, "json": True, "tool_calls": True}
            ),
            "openai": ProviderManifest(
                provider="openai",
                supported_capabilities={
                    ArovaCapability.AROVA_CAPABILITY_FAST_CHAT,
                    ArovaCapability.AROVA_CAPABILITY_REASONING,
                    ArovaCapability.AROVA_CAPABILITY_CODING,
                    ArovaCapability.AROVA_CAPABILITY_RESUME_WORKSPACE,
                    ArovaCapability.AROVA_CAPABILITY_SUMMARIZE,
                    ArovaCapability.AROVA_CAPABILITY_AMBIGUITY_ROUTING,
                    ArovaCapability.AROVA_CAPABILITY_VISION
                },
                limits={"context": 128000, "images": True, "json": True, "tool_calls": True}
            ),
            "ollama": ProviderManifest(
                provider="ollama",
                supported_capabilities={
                    ArovaCapability.AROVA_CAPABILITY_FAST_CHAT,
                    ArovaCapability.AROVA_CAPABILITY_REASONING,
                    ArovaCapability.AROVA_CAPABILITY_CODING,
                    ArovaCapability.AROVA_CAPABILITY_RESUME_WORKSPACE,
                    ArovaCapability.AROVA_CAPABILITY_SUMMARIZE,
                    ArovaCapability.AROVA_CAPABILITY_AMBIGUITY_ROUTING,
                    ArovaCapability.AROVA_CAPABILITY_EMBEDDING
                },
                limits={"context": 32768, "images": False, "json": True, "tool_calls": False}
            ),
            "anthropic": ProviderManifest(
                provider="anthropic",
                supported_capabilities={
                    ArovaCapability.AROVA_CAPABILITY_FAST_CHAT,
                    ArovaCapability.AROVA_CAPABILITY_REASONING,
                    ArovaCapability.AROVA_CAPABILITY_CODING,
                    ArovaCapability.AROVA_CAPABILITY_RESUME_WORKSPACE,
                    ArovaCapability.AROVA_CAPABILITY_SUMMARIZE,
                    ArovaCapability.AROVA_CAPABILITY_AMBIGUITY_ROUTING,
                    ArovaCapability.AROVA_CAPABILITY_VISION
                },
                limits={"context": 200000, "images": True, "json": True, "tool_calls": True}
            ),
            "gemini": ProviderManifest(
                provider="gemini",
                supported_capabilities={
                    ArovaCapability.AROVA_CAPABILITY_FAST_CHAT,
                    ArovaCapability.AROVA_CAPABILITY_REASONING,
                    ArovaCapability.AROVA_CAPABILITY_CODING,
                    ArovaCapability.AROVA_CAPABILITY_RESUME_WORKSPACE,
                    ArovaCapability.AROVA_CAPABILITY_SUMMARIZE,
                    ArovaCapability.AROVA_CAPABILITY_AMBIGUITY_ROUTING,
                    ArovaCapability.AROVA_CAPABILITY_VISION
                },
                limits={"context": 1000000, "images": True, "json": True, "tool_calls": True}
            ),
            "openrouter": ProviderManifest(
                provider="openrouter",
                supported_capabilities={
                    ArovaCapability.AROVA_CAPABILITY_FAST_CHAT,
                    ArovaCapability.AROVA_CAPABILITY_REASONING,
                    ArovaCapability.AROVA_CAPABILITY_CODING,
                    ArovaCapability.AROVA_CAPABILITY_RESUME_WORKSPACE,
                    ArovaCapability.AROVA_CAPABILITY_SUMMARIZE,
                    ArovaCapability.AROVA_CAPABILITY_AMBIGUITY_ROUTING,
                    ArovaCapability.AROVA_CAPABILITY_VISION
                },
                limits={"context": 131072, "images": True, "json": True, "tool_calls": True}
            )
        }
        # Populate initial baseline fallback profiles so zero network calls are required offline
        self._init_baseline_candidates()
        self._load_from_cache()

    def _init_baseline_candidates(self):
        """
        Curated fallback profiles if live network discovery is unreachable on clean boot.
        """
        self._candidates["groq"] = [
            ModelCandidate(
                id="llama-3.3-70b-versatile", provider="groq", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=420, cost_per_1k_tokens=0.59, selection_reason=["Baseline Groq fast chat model"]
            ),
            ModelCandidate(
                id="qwen-2.5-32b", provider="groq", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=510, cost_per_1k_tokens=0.65, selection_reason=["Baseline Groq reasoning model"]
            ),
            ModelCandidate(
                id="llama-3.1-8b-instant", provider="groq", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=210, cost_per_1k_tokens=0.05, selection_reason=["Baseline Groq instant low-latency model"]
            )
        ]
        self._candidates["openai"] = [
            ModelCandidate(
                id="gpt-4o-mini", provider="openai", context_window=128000,
                supports_tools=True, supports_images=True, supports_reasoning=False, supports_json=True,
                latency_ms=450, cost_per_1k_tokens=0.15, selection_reason=["Baseline OpenAI fast model"]
            ),
            ModelCandidate(
                id="gpt-4o", provider="openai", context_window=128000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=850, cost_per_1k_tokens=2.50, selection_reason=["Baseline OpenAI reasoning model"]
            )
        ]
        self._candidates["ollama"] = [
            ModelCandidate(
                id="llama3", provider="ollama", context_window=8192,
                supports_tools=False, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=1200, cost_per_1k_tokens=0.0, selection_reason=["Baseline local Llama3 model"]
            ),
            ModelCandidate(
                id="qwen2.5:14b", provider="ollama", context_window=32768,
                supports_tools=False, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=1600, cost_per_1k_tokens=0.0, selection_reason=["Baseline local Qwen reasoning model"]
            )
        ]
        self._candidates["anthropic"] = [
            ModelCandidate(
                id="claude-3-5-sonnet-20241022", provider="anthropic", context_window=200000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=650, cost_per_1k_tokens=3.00, selection_reason=["Baseline Anthropic coding and reasoning model"]
            ),
            ModelCandidate(
                id="claude-3-5-haiku-20241022", provider="anthropic", context_window=200000,
                supports_tools=True, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=350, cost_per_1k_tokens=0.80, selection_reason=["Baseline Anthropic fast chat model"]
            )
        ]
        self._candidates["gemini"] = [
            ModelCandidate(
                id="gemini-1.5-pro", provider="gemini", context_window=1000000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=750, cost_per_1k_tokens=1.25, selection_reason=["Baseline Google Gemini long-context reasoning model"]
            ),
            ModelCandidate(
                id="gemini-1.5-flash", provider="gemini", context_window=1000000,
                supports_tools=True, supports_images=True, supports_reasoning=False, supports_json=True,
                latency_ms=300, cost_per_1k_tokens=0.07, selection_reason=["Baseline Google Gemini fast chat model"]
            )
        ]
        self._candidates["openrouter"] = [
            ModelCandidate(
                id="deepseek/deepseek-r1", provider="openrouter", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=550, cost_per_1k_tokens=0.55, selection_reason=["Baseline OpenRouter DeepSeek reasoning model"]
            ),
            ModelCandidate(
                id="anthropic/claude-3.5-sonnet", provider="openrouter", context_window=200000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=650, cost_per_1k_tokens=3.00, selection_reason=["Baseline OpenRouter Claude coding model"]
            )
        ]

    def _load_from_cache(self):
        try:
            if os.path.exists(self.cache_path):
                with open(self.cache_path, "r") as f:
                    data = json.load(f)
                    if data.get("version") == self.version and "candidates" in data:
                        for prov, items in data["candidates"].items():
                            if prov in self._candidates:
                                self._candidates[prov] = [
                                    ModelCandidate(**{k: v for k, v in item.items() if k in ModelCandidate.__annotations__})
                                    for item in items
                                ]
                logger.info("ModelRegistry loaded candidates from cache (%s)", self.cache_path)
        except Exception as e:
            logger.warning("Failed to load model cache: %s", e)

    def _save_to_cache(self):
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w") as f:
                json.dump({
                    "version": self.version,
                    "updated_at": time.time(),
                    "candidates": {
                        prov: [c.to_dict() for c in c_list]
                        for prov, c_list in self._candidates.items()
                    }
                }, f, indent=2)
        except Exception as e:
            logger.error("Failed to save model cache: %s", e)

    async def discover_and_cache(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Queries active provider endpoints right on startup or when requested via manual UI refresh button.
        """
        from arova.core.config.manager import get_config_manager
        manager = get_config_manager()
        saved_providers = manager.load_providers()
        updated_any = False

        async with aiohttp.ClientSession() as session:
            # 1. Discover Groq
            groq_key = os.environ.get("GROQ_API_KEY", "").strip() or (saved_providers.get("groq", {}).get("api_keys", [""])[0])
            if groq_key:
                try:
                    headers = {"Authorization": f"Bearer {groq_key}"}
                    async with session.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=5.0) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            models = data.get("data", [])
                            if models:
                                live_list = []
                                for m in models:
                                    m_id = m.get("id", "")
                                    if not m_id or "whisper" in m_id or "tts" in m_id or "embed" in m_id:
                                        continue
                                    live_list.append(ModelCandidate(
                                        id=m_id, provider="groq",
                                        context_window=131072 if "70b" in m_id or "3.3" in m_id else 32768,
                                        supports_tools=True, supports_images="vision" in m_id,
                                        supports_reasoning="qwen" in m_id or "r1" in m_id or "deepseek" in m_id,
                                        supports_json=True, latency_ms=400 if "70b" in m_id else 210,
                                        cost_per_1k_tokens=0.59 if "70b" in m_id else 0.05,
                                        selection_reason=["Discovered via Groq live API catalog"]
                                    ))
                                if live_list:
                                    self._candidates["groq"] = live_list
                                    updated_any = True
                except Exception as e:
                    logger.warning("Groq live discovery failed, using baseline/cache: %s", e)

            # 2. Discover Ollama
            ollama_host = saved_providers.get("ollama", {}).get("host", "http://localhost:11434")
            try:
                async with session.get(f"{ollama_host}/api/tags", timeout=3.0) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = data.get("models", [])
                        if models:
                            live_list = []
                            for m in models:
                                m_name = m.get("name", "")
                                if not m_name:
                                    continue
                                live_list.append(ModelCandidate(
                                    id=m_name, provider="ollama",
                                    context_window=32768 if "qwen" in m_name else 8192,
                                    supports_tools=False, supports_images="vision" in m_name or "llava" in m_name,
                                    supports_reasoning="qwen" in m_name or "deepseek" in m_name,
                                    supports_json=True, latency_ms=1300, cost_per_1k_tokens=0.0,
                                    selection_reason=["Discovered via local Ollama tags"]
                                ))
                            if live_list:
                                self._candidates["ollama"] = live_list
                                updated_any = True
            except Exception as e:
                logger.debug("Ollama live discovery unreachable: %s", e)

        if updated_any or force_refresh:
            self._save_to_cache()

        return self.get_summary_report()

    def resolve(self, capability: ArovaCapability, quality: QualityTier = QualityTier.BALANCED,
                provider_id: Optional[str] = None) -> ModelCandidate:
        """
        Resolves the optimal ModelCandidate for a requested capability and quality tier.
        Ranks all available candidates using CandidateScorer and returns the top choice.
        """
        all_candidates = []
        if provider_id and provider_id in self._candidates:
            all_candidates = list(self._candidates[provider_id])
        else:
            for c_list in self._candidates.values():
                all_candidates.extend(c_list)

        if not all_candidates:
            # Emergency fallback if everything is empty
            return ModelCandidate(
                id="llama-3.3-70b-versatile", provider="groq", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=420, cost_per_1k_tokens=0.59, selection_reason=["Emergency default candidate"]
            )

        # Score and rank all candidates against this capability & quality tier
        ranked = []
        for c in all_candidates:
            score = CandidateScorer.score_candidate(c, capability, quality)
            if score > 0.0:
                ranked.append((score, c))

        ranked.sort(key=lambda x: x[0], reverse=True)
        if ranked:
            top_candidate = ranked[0][1]
            logger.debug("ModelRegistry.resolve(%s, %s) -> %s (score=%.1f)", capability.value, quality.value, top_candidate.id, top_candidate.score)
            return top_candidate
        else:
            return all_candidates[0]

    def get_summary_report(self) -> Dict[str, Any]:
        """
        Provides complete telemetry breakdown for UI Settings and health checks.
        """
        return {
            "registry_version": self.version,
            "providers": {
                prov: {
                    "available_models": len(c_list),
                    "candidates": [c.to_dict() for c in c_list]
                }
                for prov, c_list in self._candidates.items()
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.get_summary_report()


# Singleton accessor
_GLOBAL_REGISTRY: Optional[ModelRegistry] = None

def get_model_registry() -> ModelRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ModelRegistry()
    return _GLOBAL_REGISTRY
