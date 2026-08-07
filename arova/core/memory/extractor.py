import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from arova.core.session import ConversationTurn
from arova.core.memory.storage import MemoryEntry

class MemoryExtractor:
    """
    LLM pipeline to score and extract semantic/preference facts from raw conversations.
    In a real implementation, this invokes an LLM structured completion.
    For now, it's a structural mock demonstrating the pipeline.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.orchestrator = None
        
    def set_orchestrator(self, orchestrator: Any):
        self.orchestrator = orchestrator
        
    async def extract_from_turn(self, turn: ConversationTurn) -> List[MemoryEntry]:
        """
        Takes an archived turn and extracts Candidate Memories.
        Example: "User says: Play some jazz." -> MemoryEntry(type="preference", content="Likes jazz")
        """
        extracted = []
        
        if not self.orchestrator:
            logging.warning("MemoryExtractor: No orchestrator set, cannot extract memories.")
            return extracted
            
        system_prompt = """
You are an ambient semantic memory extractor.
Analyze the user's latest transcript and the assistant's response.
Extract any NEW, PERSISTENT facts, entities, or preferences about the user.
Do not extract transient state (e.g. "user is tired right now").

Return a JSON array of objects. Each object must have:
- type: "entity" or "preference" or "fact"
- content: A concise, standalone statement (e.g. "User's name is Sarthak", "User's bank account is 123")
- category: A broad string like "pets", "education", "finances", "development", "general"
- why_remembered: A brief explanation of why this is being saved (e.g. "User explicitly stated their pet's name")
- continuity_value: A float between 0.0 and 1.0 representing how useful this is for long-term ambient continuity
- sensitivity_tier: An integer 1, 2, or 3.
   1 (Operational): Safe, tech stack, UI preferences.
   2 (Personal): Pets, hobbies, education, life context.
   3 (Sensitive): Finances, API keys, passwords, medical, exact locations, legal.

If there are no persistent facts to extract, return an empty array [].
Respond ONLY with valid JSON array.
"""

        messages = [
            {"role": "user", "content": f"User Transcript: {turn.user_transcript}\nAssistant Response: {turn.assistant_response}"}
        ]
        
        try:
            # We use standard depth since this runs asynchronously in the background and shouldn't block
            from arova.core.models.schema import ReasoningDepth, ReasoningBudget
            result = await self.orchestrator.invoke_structured(
                messages=messages,
                system_prompt=system_prompt,
                depth=ReasoningDepth.STANDARD,
                budget=ReasoningBudget(max_tokens=512)
            )
            
            # The orchestrator returns parsed JSON if the provider gave valid JSON, else {"content": "..."}
            # We expect a JSON array of dicts — OR a single dict with memories key.
            data = result
            data = self._coerce_to_list(data)

            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "content" in item:
                        try:
                            extracted.append(MemoryEntry(
                                id=str(uuid.uuid4()),
                                type=item.get("type", "fact"),
                                content=item["content"],
                                source_turn_id=turn.turn_id,
                                category=item.get("category", "general"),
                                why_remembered=item.get("why_remembered", "Extracted from conversation"),
                                continuity_value=float(item.get("continuity_value", 0.5)),
                                sensitivity_tier=int(item.get("sensitivity_tier", 2)),
                                approval_state="pending"
                            ))
                        except Exception as item_err:
                            logging.warning(f"MemoryExtractor: skipped bad item: {item_err}")
        except Exception as e:
            logging.error(f"MemoryExtractor LLM call failed: {e}")

        # Heuristic fallback when LLM parse fails but turn clearly has durable facts
        if not extracted:
            extracted = self._heuristic_extract(turn)

        if extracted:
            logging.info(f"MemoryExtractor produced {len(extracted)} candidate memories: {[m.content for m in extracted]}")

        return extracted

    def _coerce_to_list(self, data: Any) -> list:
        """Best-effort: turn orchestrator output into a list of memory dicts."""
        import re
        import ast

        if data is None:
            return []
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Already a single memory object
            if "content" in data and ("type" in data or "category" in data):
                return [data]
            # Wrapped forms
            for key in ("memories", "items", "results", "data", "extractions"):
                if isinstance(data.get(key), list):
                    return data[key]
            # Raw string content from provider adapter
            if "content" in data and isinstance(data["content"], str):
                return self._parse_text_array(data["content"])
            return []
        if isinstance(data, str):
            return self._parse_text_array(data)
        return []

    def _parse_text_array(self, text: str) -> list:
        import re
        import ast

        if not text or not str(text).strip():
            return []
        text = str(text).strip()
        # Strip markdown fences
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # Truncated JSON arrays are common (max_tokens). Try to salvage complete objects.
        candidates = [text]
        # If truncated mid-array, close it
        if text.startswith("[") and not text.rstrip().endswith("]"):
            # Drop incomplete trailing object
            last_brace = text.rfind("}")
            if last_brace > 0:
                candidates.append(text[: last_brace + 1] + "]")
            candidates.append(text + "]")

        for cand in candidates:
            try:
                parsed = json.loads(cand)
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, dict):
                    return [parsed]
            except json.JSONDecodeError:
                pass
            try:
                parsed = ast.literal_eval(cand)
                if isinstance(parsed, list):
                    logging.info("MemoryExtractor: Parsed via ast.literal_eval")
                    return parsed
            except (ValueError, SyntaxError):
                pass
            try:
                fixed = cand.replace("'", '"')
                parsed = json.loads(fixed)
                if isinstance(parsed, list):
                    logging.info("MemoryExtractor: Parsed via quote-fix fallback")
                    return parsed
            except json.JSONDecodeError:
                pass

        # Extract individual {...} objects via regex as last resort
        objs = re.findall(r"\{[^{}]+\}", text, re.DOTALL)
        recovered = []
        for chunk in objs:
            try:
                obj = json.loads(chunk)
                if isinstance(obj, dict) and "content" in obj:
                    recovered.append(obj)
            except json.JSONDecodeError:
                try:
                    obj = ast.literal_eval(chunk)
                    if isinstance(obj, dict) and "content" in obj:
                        recovered.append(obj)
                except (ValueError, SyntaxError):
                    pass

        # Truncated mid-object: pull out "content": "..." even if braces never closed
        if not recovered:
            content_hits = re.findall(
                r'"content"\s*:\s*"((?:\\.|[^"\\])*)"',
                text,
            )
            type_hits = re.findall(r'"type"\s*:\s*"([^"]+)"', text)
            cat_hits = re.findall(r'"category"\s*:\s*"([^"]+)"', text)
            for i, content in enumerate(content_hits):
                recovered.append({
                    "type": type_hits[i] if i < len(type_hits) else "fact",
                    "content": content.encode("utf-8").decode("unicode_escape") if "\\" in content else content,
                    "category": cat_hits[i] if i < len(cat_hits) else "general",
                    "why_remembered": "Recovered from truncated extractor JSON",
                    "continuity_value": 0.5,
                    "sensitivity_tier": 2,
                })

        if recovered:
            logging.info(f"MemoryExtractor: Recovered {len(recovered)} objects from truncated JSON")
            return recovered

        logging.warning(f"MemoryExtractor: All parsers failed for: {text[:200]}")
        return []

    def _heuristic_extract(self, turn: ConversationTurn) -> List[MemoryEntry]:
        """
        Zero-LLM fallback: if the user clearly stated a durable study/work fact,
        keep a single candidate so memory isn't silently empty.
        """
        text = (turn.user_transcript or "").strip()
        if len(text) < 40:
            return []
        lower = text.lower()
        content = None
        category = "general"
        if any(k in lower for k in ("studying", "learn", "course", "exam", "class")):
            # Keep first sentence-ish as a compact fact
            snippet = text.replace("\n", " ").strip()
            if len(snippet) > 180:
                snippet = snippet[:177] + "..."
            content = f"User learning context: {snippet}"
            category = "education"
        elif any(k in lower for k in ("i prefer", "i like", "i always", "my name is")):
            snippet = text.replace("\n", " ").strip()[:180]
            content = f"User preference/fact: {snippet}"
            category = "preference"

        if not content:
            return []
        return [MemoryEntry(
            id=str(uuid.uuid4()),
            type="fact",
            content=content,
            source_turn_id=turn.turn_id,
            category=category,
            why_remembered="Heuristic fallback after LLM parse failure",
            continuity_value=0.55,
            sensitivity_tier=2,
            approval_state="pending",
        )]
