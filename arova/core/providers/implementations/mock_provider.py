import logging
from typing import List, Dict, Any, Set, AsyncGenerator
from arova.core.providers.base import CognitiveProvider
from arova.core.providers.capabilities import Capability

logger = logging.getLogger(__name__)

MOCK_RESPONSE = "I currently have no inference provider available. My presence is still here — threads, memory, and continuity are intact — but I cannot generate new responses right now."

# === TIER 1 MOAT: Grounded mock that cites VERBATIM ground truth when available ===
def _grounded_mock_from_prompt(system_prompt: str, messages: List[Dict[str, Any]]) -> str:
    """If system_prompt contains GROUND TRUTH, synthesize a verbatim answer instead of degraded."""
    if system_prompt and "[GROUND TRUTH" in system_prompt:
        # Try to extract workspace title, goal, resources
        import re
        # Extract Workspace line
        title_match = re.search(r'Workspace:\s*(.+)', system_prompt)
        title = title_match.group(1).strip() if title_match else "your workspace"
        # Remove hedging prefix if present
        title = title.replace("I think the goal is:", "").strip()
        goal_match = re.search(r'Goal:\s*(.+)', system_prompt)
        goal = goal_match.group(1).strip() if goal_match else ""
        # Check for mentioned resources — highest priority for @ queries
        if "[MENTIONED RESOURCES" in system_prompt:
            # Extract file excerpt
            excerpt_match = re.search(r'--- FILE: (.+?) ---\n(.+?)\n--- END FILE ---', system_prompt, re.DOTALL)
            if excerpt_match:
                fpath = excerpt_match.group(1).strip()
                return f"You @-mentioned `{fpath}` — I see the verbatim content above. Based on that, the flow around that file is what you asked about. Want me to trace it? (Grounded mock — add an LLM key for deeper reasoning)"
            # Fallback: if mention block present but regex missed (e.g., test), extract @ from messages
            if messages:
                for m in reversed(messages):
                    if m.get("role") == "user" and "@" in m.get("content", ""):
                        import re as _re2
                        at_match = _re2.search(r'@([\w./\-]+)', m.get("content", ""))
                        if at_match:
                            return f"You @-mentioned `{at_match.group(1)}` — I see the verbatim content above. Based on that, the flow around that file is what you asked about. Want me to trace it? (Grounded mock — add an LLM key for deeper reasoning)"
        # Check for search results — for 'find/search' queries, cite verbatim hits
        if "[SEARCH RESULTS" in system_prompt:
            # Try to extract first hit title
            import re as _re_s
            # Pattern: - [Kind] Title: summary...
            search_section = system_prompt.split("[SEARCH RESULTS")[1] if "[SEARCH RESULTS" in system_prompt else system_prompt
            hit_match = _re_s.search(r'- \[(.+?)\]\s+(.+?):', search_section)
            if hit_match:
                kind = hit_match.group(1)
                title = hit_match.group(2).strip()[:80]
                # Count hits
                hit_count = search_section.count("- [")
                return f"Found via unified search — **{title}** [{kind}] + {max(0, hit_count-1)} more verbatim hits in [SEARCH RESULTS] above. No hallucination. (Grounded mock — add LLM for synthesis)"
            return f"Grounded search mock: I found verbatim hits in your unified index for your query. See [SEARCH RESULTS] above. (Add LLM for reasoning)"
        # Check for verbatim resources
        if "- [file]" in system_prompt or "- [terminal]" in system_prompt or "- [url]" in system_prompt:
            # Extract first file
            file_match = re.search(r'- \[(?:file|terminal|url|repository)\]\s*([^\s]+)', system_prompt)
            cited = file_match.group(1).split('/')[-1] if file_match else "your recent files"
            # Low confidence hedge — only if HUMILITY section present (not just instruction)
            is_low = "[HUMILITY INSTRUCTION]" in system_prompt and "LOW" in system_prompt
            hedge = "I think " if is_low else ""
            # Find user query
            last_user = ""
            if messages:
                for m in reversed(messages):
                    if m.get("role") == "user":
                        last_user = m.get("content", "")[:80]
                        break
            if "where" in last_user.lower() or "what was" in last_user.lower() or "resume" in last_user.lower():
                return f"{hedge}You were working on **{title}** — {goal[:120] if goal else 'continuing your trajectory'}. Last observed: `{cited}`. Check ground truth above for exact files. (Grounded mock — no LLM key, but still verbatim)"
        # Fallback grounded but generic
        return f"Grounded mock: I see your VERBATIM ground truth in the prompt ({len(system_prompt)} chars). Ask `where was I?` or `@file.py what's stuck?` and I'll cite exact files. (Add Groq/OpenAI key for full LLM)"
    return MOCK_RESPONSE


class MockProvider(CognitiveProvider):
    """
    First-class fallback provider.
    When all real providers are down, the room stays alive.
    Threads persist. Memory persists. Orb persists.
    Only cognition degrades gracefully.
    """

    @property
    def name(self) -> str:
        return "mock"

    @property
    def supported_capabilities(self) -> Set[Capability]:
        # Only support CHAT so user gets explicit fallback message in UI. Never support embeddings or summaries.
        return {Capability.CHAT}

    async def generate(self, messages: List[Dict[str, Any]], system_prompt: str,
                       model: str = "", max_tokens: int = 512) -> str:
        grounded = _grounded_mock_from_prompt(system_prompt, messages)
        if grounded != MOCK_RESPONSE:
            logger.info("MockProvider: Returning GROUNDED mock (verbatim ground truth cited)")
            return grounded
        logger.warning("MockProvider: Returning degraded response (no real provider available).")
        return MOCK_RESPONSE

    async def stream(self, messages: List[Dict[str, Any]], system_prompt: str,
                     model: str = "", max_tokens: int = 512) -> AsyncGenerator[str, None]:
        grounded = _grounded_mock_from_prompt(system_prompt, messages)
        if grounded != MOCK_RESPONSE:
            logger.info("MockProvider: Streaming GROUNDED mock")
            # Stream in chunks to mimic LLM
            for i in range(0, len(grounded), 60):
                yield grounded[i:i+60]
            return
        logger.warning("MockProvider: Streaming degraded response.")
        yield MOCK_RESPONSE

    async def embed(self, text: str) -> List[float]:
        raise RuntimeError("Inference Unavailable: Cannot generate real embeddings without a healthy provider.")
