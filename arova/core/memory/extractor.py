import uuid
import json
import logging
from typing import List, Dict, Any
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
                budget=ReasoningBudget(max_tokens=256)
            )
            
            # The orchestrator returns parsed JSON if the provider gave valid JSON, else {"content": "..."}
            # We expect a JSON array of dicts.
            data = result
            if isinstance(data, dict) and "content" in data:
                # Try to parse string content if adapter failed to parse it
                try:
                    import json
                    text = data["content"].strip()
                    if text.startswith("```json"): text = text[7:]
                    if text.startswith("```"): text = text[3:]
                    if text.endswith("```"): text = text[:-3]
                    text = text.strip()
                    
                    # Try standard JSON first
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        # LLMs often return Python dict syntax (single quotes) instead of JSON
                        # Try ast.literal_eval which handles Python literals safely
                        import ast
                        try:
                            data = ast.literal_eval(text)
                            logging.info(f"MemoryExtractor: Parsed via ast.literal_eval (LLM returned Python syntax)")
                        except (ValueError, SyntaxError):
                            # Last resort: try fixing common quote issues
                            fixed = text.replace("'", '"')
                            try:
                                data = json.loads(fixed)
                                logging.info(f"MemoryExtractor: Parsed via quote-fix fallback")
                            except json.JSONDecodeError:
                                logging.warning(f"MemoryExtractor: All parsers failed for: {text[:200]}")
                                data = []
                except Exception as e:
                    logging.warning(f"MemoryExtractor: Failed to parse raw string into JSON array: {e}")
                    data = []
                    
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "content" in item:
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
        except Exception as e:
            logging.error(f"MemoryExtractor LLM call failed: {e}")
            
        if extracted:
            logging.info(f"MemoryExtractor produced {len(extracted)} candidate memories: {[m.content for m in extracted]}")
            
        return extracted
