import os
import json
import time
import logging
import asyncio
try:
    import aiohttp
except ImportError:
    aiohttp = None
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
                id="openai/gpt-oss-120b", provider="groq", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=180, cost_per_1k_tokens=0.40, selection_reason=["Blazing-fast open-source OpenAI workflows on Groq LPU"]
            ),
            ModelCandidate(
                id="openai/gpt-oss-20b", provider="groq", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=90, cost_per_1k_tokens=0.10, selection_reason=["Instant sub-second enterprise API responses on Groq LPU"]
            ),
            ModelCandidate(
                id="qwen-3.6-27b", provider="groq", context_window=32768,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=140, cost_per_1k_tokens=0.25, selection_reason=["Rapid multilingual conversion and code generation on Groq LPU"]
            ),
            ModelCandidate(
                id="qwen-3-32b", provider="groq", context_window=32768,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=160, cost_per_1k_tokens=0.30, selection_reason=["High-frequency code snippet and JSON generation on Groq LPU"]
            ),
            ModelCandidate(
                id="llama-3.3-70b-versatile", provider="groq", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=260, cost_per_1k_tokens=0.59, selection_reason=["Complex agentic workflows and fast repeated reasoning round-trips"]
            ),
            ModelCandidate(
                id="llama-3.1-8b-instant", provider="groq", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=70, cost_per_1k_tokens=0.08, selection_reason=["Ultra-fast sub-second conversational interface on Groq LPU"]
            ),
            ModelCandidate(
                id="mixtral-8x22b-instruct", provider="groq", context_window=65536,
                supports_tools=True, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=220, cost_per_1k_tokens=0.50, selection_reason=["European language logic and structured database commands on Groq"]
            ),
            ModelCandidate(
                id="deepseek-r1-distill-llama-70b", provider="groq", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=280, cost_per_1k_tokens=0.75, selection_reason=["Sub-second math logic, structural coding, and open reasoning on Groq LPU"]
            )
        ]
        self._candidates["openai"] = [
            ModelCandidate(
                id="gpt-5.6-sol", provider="openai", context_window=128000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=750, cost_per_1k_tokens=3.00, selection_reason=["Flagship OpenAI creative intelligence and multimodal reasoning"]
            ),
            ModelCandidate(
                id="gpt-5.6-terra", provider="openai", context_window=128000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=450, cost_per_1k_tokens=1.20, selection_reason=["Balanced OpenAI frontier intelligence model"]
            ),
            ModelCandidate(
                id="gpt-5.6-luna", provider="openai", context_window=128000,
                supports_tools=True, supports_images=True, supports_reasoning=False, supports_json=True,
                latency_ms=200, cost_per_1k_tokens=0.15, selection_reason=["Fast high-volume text sorting and classification"]
            ),
            ModelCandidate(
                id="o3", provider="openai", context_window=200000,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=900, cost_per_1k_tokens=2.50, selection_reason=["Deep test-time compute thought chain reasoning"]
            ),
            ModelCandidate(
                id="o3-pro", provider="openai", context_window=200000,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=1200, cost_per_1k_tokens=5.00, selection_reason=["Frontier competitive coding and mathematical proofing"]
            ),
            ModelCandidate(
                id="o4-mini", provider="openai", context_window=128000,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=300, cost_per_1k_tokens=0.50, selection_reason=["High-speed autonomous agent orchestration"]
            ),
            ModelCandidate(
                id="gpt-oss-120b", provider="openai", context_window=128000,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=600, cost_per_1k_tokens=0.80, selection_reason=["Open-weight enterprise Apache 2.0 system"]
            )
        ]
        self._candidates["anthropic"] = [
            ModelCandidate(
                id="claude-fable-5", provider="anthropic", context_window=1000000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=700, cost_per_1k_tokens=4.00, selection_reason=["Multi-step autonomous business strategies and technical auditing"]
            ),
            ModelCandidate(
                id="claude-sonnet-5", provider="anthropic", context_window=1000000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=500, cost_per_1k_tokens=2.00, selection_reason=["Software engineering, daily programming, and heavy markdown"]
            ),
            ModelCandidate(
                id="claude-opus-4.8", provider="anthropic", context_window=1000000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=850, cost_per_1k_tokens=5.00, selection_reason=["1M token deep multi-document research"]
            ),
            ModelCandidate(
                id="claude-mythos-5", provider="anthropic", context_window=1000000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=800, cost_per_1k_tokens=5.00, selection_reason=["Experimental sandbox reasoning and data analytics"]
            )
        ]
        self._candidates["gemini"] = [
            ModelCandidate(
                id="gemini-3.1-pro", provider="gemini", context_window=2000000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=650, cost_per_1k_tokens=1.50, selection_reason=["2M token active code repository and full video review"]
            ),
            ModelCandidate(
                id="gemini-3.7-flash", provider="gemini", context_window=2000000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=220, cost_per_1k_tokens=0.10, selection_reason=["Rapid developer feedback loops and fast live chat"]
            ),
            ModelCandidate(
                id="gemini-3.6-flash", provider="gemini", context_window=2000000,
                supports_tools=True, supports_images=True, supports_reasoning=False, supports_json=True,
                latency_ms=260, cost_per_1k_tokens=0.07, selection_reason=["Foundation layer for automated content filtering"]
            ),
            ModelCandidate(
                id="gemini-3.5-flash-lite", provider="gemini", context_window=1000000,
                supports_tools=True, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=150, cost_per_1k_tokens=0.03, selection_reason=["High-volume web scraping and data indexing"]
            ),
            ModelCandidate(
                id="gemini-3.1-flash-image", provider="gemini", context_window=1000000,
                supports_tools=False, supports_images=True, reasoning=False, supports_json=True,
                latency_ms=300, cost_per_1k_tokens=0.15, selection_reason=["Nano Banana 2 graphic formatting and video summaries"]
            )
        ]
        self._candidates["ollama"] = [
            ModelCandidate(
                id="gpt-oss:120b", provider="ollama", context_window=65536,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=1400, cost_per_1k_tokens=0.0, selection_reason=["Local GPT OSS 120B open-weight model"]
            ),
            ModelCandidate(
                id="qwen3:32b", provider="ollama", context_window=32768,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=1100, cost_per_1k_tokens=0.0, selection_reason=["Local Qwen 3 reasoning and coding model"]
            ),
            ModelCandidate(
                id="qwen2.5-coder:32b", provider="ollama", context_window=32768,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=1100, cost_per_1k_tokens=0.0, selection_reason=["Local Qwen 2.5 Coder specialist"]
            ),
            ModelCandidate(
                id="llama3.3:70b", provider="ollama", context_window=128000,
                supports_tools=True, supports_images=False, supports_reasoning=False, supports_json=True,
                latency_ms=1300, cost_per_1k_tokens=0.0, selection_reason=["Local Llama 3.3 70B model"]
            ),
            ModelCandidate(
                id="deepseek-r1:32b", provider="ollama", context_window=65536,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=1500, cost_per_1k_tokens=0.0, selection_reason=["Local DeepSeek R1 reasoning model"]
            )
        ]
        self._candidates["openrouter"] = [
            ModelCandidate(
                id="qwen/qwen-3-32b", provider="openrouter", context_window=131072,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=350, cost_per_1k_tokens=0.20, selection_reason=["OpenRouter Qwen 3 reasoning model"]
            ),
            ModelCandidate(
                id="deepseek/deepseek-r1", provider="openrouter", context_window=128000,
                supports_tools=True, supports_images=False, supports_reasoning=True, supports_json=True,
                latency_ms=650, cost_per_1k_tokens=0.55, selection_reason=["OpenRouter DeepSeek R1 reasoning model"]
            ),
            ModelCandidate(
                id="anthropic/claude-sonnet-5", provider="openrouter", context_window=200000,
                supports_tools=True, supports_images=True, supports_reasoning=True, supports_json=True,
                latency_ms=500, cost_per_1k_tokens=3.00, selection_reason=["OpenRouter Claude Sonnet 5 model"]
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
        Dynamically probes provider endpoints (HyprVoice-style live auto-discovery)
        with denylist filtering and local 24h caching TTL.
        """
        from arova.core.config.manager import get_config_manager
        manager = get_config_manager()
        saved_providers = manager.load_providers()
        updated_any = False
        denylist_pattern = re.compile(r'whisper|tts|guard|embed|moderation|audio|image|playai|safeguard|realtime|dall-e|prompt-guard|bison|gecko|aqa', re.IGNORECASE)

        if not aiohttp:
            logger.warning("aiohttp not installed; skipping remote live discovery.")
            return self.get_summary_report()

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
                                    if not m_id or denylist_pattern.search(m_id):
                                        continue
                                    live_list.append(ModelCandidate(
                                        id=m_id, provider="groq",
                                        context_window=131072 if "70b" in m_id or "3.3" in m_id or "120b" in m_id else 32768,
                                        supports_tools=True, supports_images="vision" in m_id,
                                        supports_reasoning="qwen" in m_id or "r1" in m_id or "deepseek" in m_id or "oss" in m_id,
                                        supports_json=True, latency_ms=260 if "70b" in m_id else 140,
                                        cost_per_1k_tokens=0.59 if "70b" in m_id else 0.10,
                                        selection_reason=["Discovered via live Groq LPU catalog"]
                                    ))
                                if live_list:
                                    self._candidates["groq"] = live_list
                                    updated_any = True
                except Exception as e:
                    logger.warning("Groq live discovery failed: %s", e)

            # 2. Discover OpenAI
            openai_key = os.environ.get("OPENAI_API_KEY", "").strip() or (saved_providers.get("openai", {}).get("api_keys", [""])[0])
            if openai_key:
                try:
                    headers = {"Authorization": f"Bearer {openai_key}"}
                    async with session.get("https://api.openai.com/v1/models", headers=headers, timeout=5.0) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            models = data.get("data", [])
                            if models:
                                live_list = []
                                for m in models:
                                    m_id = m.get("id", "")
                                    if not m_id or denylist_pattern.search(m_id):
                                        continue
                                    live_list.append(ModelCandidate(
                                        id=m_id, provider="openai",
                                        context_window=200000 if "o3" in m_id or "o1" in m_id else 128000,
                                        supports_tools=True, supports_images="gpt-4" in m_id or "gpt-5" in m_id or "sol" in m_id,
                                        supports_reasoning="o3" in m_id or "o1" in m_id or "o4" in m_id or "sol" in m_id,
                                        supports_json=True, latency_ms=450,
                                        cost_per_1k_tokens=1.50,
                                        selection_reason=["Discovered via live OpenAI catalog"]
                                    ))
                                if live_list:
                                    self._candidates["openai"] = live_list
                                    updated_any = True
                except Exception as e:
                    logger.warning("OpenAI live discovery failed: %s", e)

            # 3. Discover Google Gemini
            gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or (saved_providers.get("gemini", {}).get("api_keys", [""])[0])
            if gemini_key:
                try:
                    async with session.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}", timeout=5.0) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            models = data.get("models", [])
                            if models:
                                live_list = []
                                for m in models:
                                    m_name = (m.get("name", "")).replace("models/", "")
                                    if not m_name or denylist_pattern.search(m_name):
                                        continue
                                    methods = m.get("supportedGenerationMethods", [])
                                    if "generateContent" not in methods:
                                        continue
                                    live_list.append(ModelCandidate(
                                        id=m_name, provider="gemini",
                                        context_window=2000000 if "pro" in m_name or "flash" in m_name else 1000000,
                                        supports_tools=True, supports_images=True,
                                        supports_reasoning="pro" in m_name or "3.7" in m_name or "3.1" in m_name,
                                        supports_json=True, latency_ms=250,
                                        cost_per_1k_tokens=0.10,
                                        selection_reason=["Discovered via live Google Gemini catalog"]
                                    ))
                                if live_list:
                                    self._candidates["gemini"] = live_list
                                    updated_any = True
                except Exception as e:
                    logger.warning("Gemini live discovery failed: %s", e)

            # 4. Discover Anthropic
            anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip() or (saved_providers.get("anthropic", {}).get("api_keys", [""])[0])
            if anthropic_key:
                try:
                    headers = {
                        "x-api-key": anthropic_key,
                        "anthropic-version": "2023-06-01"
                    }
                    async with session.get("https://api.anthropic.com/v1/models", headers=headers, timeout=5.0) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            models = data.get("data", [])
                            if models:
                                live_list = []
                                for m in models:
                                    m_id = m.get("id", "")
                                    if not m_id or denylist_pattern.search(m_id):
                                        continue
                                    live_list.append(ModelCandidate(
                                        id=m_id, provider="anthropic",
                                        context_window=1000000 if "fable" in m_id or "sonnet" in m_id or "opus" in m_id else 200000,
                                        supports_tools=True, supports_images=True,
                                        supports_reasoning="fable" in m_id or "sonnet" in m_id or "mythos" in m_id or "opus" in m_id,
                                        supports_json=True, latency_ms=550,
                                        cost_per_1k_tokens=2.00,
                                        selection_reason=["Discovered via live Anthropic catalog"]
                                    ))
                                if live_list:
                                    self._candidates["anthropic"] = live_list
                                    updated_any = True
                except Exception as e:
                    logger.warning("Anthropic live discovery failed: %s", e)

            # 5. Discover Ollama (Local)
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
                                if not m_name or denylist_pattern.search(m_name):
                                    continue
                                live_list.append(ModelCandidate(
                                    id=m_name, provider="ollama",
                                    context_window=65536 if "oss" in m_name or "r1" in m_name else 32768,
                                    supports_tools=False, supports_images="vision" in m_name or "llava" in m_name,
                                    supports_reasoning="qwen" in m_name or "r1" in m_name or "deepseek" in m_name or "oss" in m_name,
                                    supports_json=True, latency_ms=1200, cost_per_1k_tokens=0.0,
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
