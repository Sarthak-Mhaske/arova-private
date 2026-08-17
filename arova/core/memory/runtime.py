import asyncio
import logging
import uuid
import os
import time
from typing import Any, Dict, List
from arova.core.events import RuntimeEventBus, EventPayload
from arova.core.memory.storage import MemoryStorage, MemoryEntry
from arova.core.memory.extractor import MemoryExtractor
from arova.core.session import ConversationTurn
logger = logging.getLogger(__name__)

class MemoryRuntime:
    """
    Async queryable Memory Layer. Listens to events to build episodic memory and
    extracts semantic facts.
    """
    def __init__(self, event_bus: RuntimeEventBus, config: Dict[str, Any]):
        self.event_bus = event_bus
        self.config = config
        
        xdg_runtime = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        arova_dir = os.path.join(xdg_runtime, "arova")
        os.makedirs(arova_dir, exist_ok=True)
        db_path = os.path.join(arova_dir, "memory.sqlite")
        
        self.storage = MemoryStorage(db_path)
        self.extractor = MemoryExtractor(config)
        from arova.core.config.manager import get_config_manager
        from arova.core.memory.memory_policy import MemoryPolicyEngine
        self.policy_engine = MemoryPolicyEngine(get_config_manager())
        self.session_only_memories: List[MemoryEntry] = []
        self._loop = None
        # === TIER 1 Vector: Hybrid semantic memory (QdrantLocal + HybridRetrieval) ===
        try:
            from arova.core.cognition.memory.vector import QdrantLocal
            self.vector_store = QdrantLocal()
            logging.info("MemoryRuntime: Vector store initialized (hybrid retrieval enabled)")
        except Exception as e:
            logging.warning(f"MemoryRuntime: Vector store init failed ({e}) -- heuristic fallback only")
            self.vector_store = None
            
        # We hook into capabilities to log them to episodic memory
        self.event_bus.subscribe("capabilities", "CAPABILITY_EXECUTION_COMPLETED", self._on_capability_completed)

    def set_orchestrator(self, orchestrator: Any):
        """Inject the model orchestrator for LLM-based extraction."""
        self.extractor.set_orchestrator(orchestrator)
        
        
    async def initialize(self):
        self._loop = asyncio.get_running_loop()
        await self.storage.initialize()
        logging.info("MemoryRuntime initialized.")
        
    def _on_capability_completed(self, payload: EventPayload):
        execution_id = getattr(payload, "execution_id", "unknown")
        turn_id = getattr(payload, "turn_id", None)
        cap_name = getattr(payload, "capability_name", "unknown")
        result = getattr(payload, "result", None)
        
        if self._loop:
            asyncio.run_coroutine_threadsafe(self.storage.append_episodic_event(
                event_id=execution_id,
                event_type="CAPABILITY_EXECUTION_COMPLETED",
                turn_id=turn_id,
                payload={"capability": cap_name, "result": result}
            ), self._loop)
        else:
            logging.error("MemoryRuntime: No event loop captured at initialization!")

    async def archive_turn(self, turn: ConversationTurn):
        """
        Called by ConversationSession when a turn drops out of the warm context window.
        We only store the episodic event here now. Semantic extraction is eager.
        """
        await self.storage.append_episodic_event(
            event_id=turn.turn_id,
            event_type="CONVERSATION_TURN",
            turn_id=turn.turn_id,
            payload={"user": turn.user_transcript, "assistant": turn.assistant_response}
        )
        
    async def extract_eagerly(self, turn: ConversationTurn):
        """
        Triggered immediately after assistant response.
        Extracts, classifies, routes via policy engine, and emits to UI or saves.
        """
        from dataclasses import asdict
        from arova.core.memory.memory_policy import StorageRoute
        
        logging.info(f"MemoryRuntime.extract_eagerly: Starting for turn={turn.turn_id}, user='{turn.user_transcript}', assistant='{turn.assistant_response[:50] if turn.assistant_response else 'None'}'")
        
        candidates = await self.extractor.extract_from_turn(turn)
        logging.info(f"MemoryRuntime.extract_eagerly: Extractor returned {len(candidates)} candidates")
        
        # Deduplicate against existing memories
        existing_memories = await self.storage.get_all_semantic_memory()
        
        for cand in candidates:
            # Check for existing memory with similar content using word overlap
            duplicate = None
            cand_words = set(cand.content.lower().split())
            for mem in existing_memories:
                mem_words = set(mem.content.lower().split())
                if not mem_words or not cand_words:
                    continue
                intersection = len(mem_words.intersection(cand_words))
                union = len(mem_words.union(cand_words))
                if union > 0 and (intersection / union) > 0.6:
                    duplicate = mem
                    break
                    
            if duplicate:
                logging.info(f"MemoryRuntime.extract_eagerly: Deduplicated candidate '{cand.content}'. Reinforcing existing memory {duplicate.id}.")
                duplicate.reinforcement_count += 1
                duplicate.last_reinforced_at = time.time()
                
                # If a pending memory is reinforced again, auto-promote it to saved
                if duplicate.approval_state == "pending" and duplicate.reinforcement_count >= 2:
                    duplicate.approval_state = "saved"
                    logging.info(f"Memory Auto-Promoted to Saved: {duplicate.content}")
                    self.event_bus.emit("memory", "MEMORY_SAVED", {"memory": asdict(duplicate)})
                    self.event_bus.emit("timeline", "create", {
                        "category": "memory",
                        "title": "Memory Promoted",
                        "description": f"Reinforced pending memory: '{duplicate.content}'",
                        "source": "memory_runtime",
                        "importance": 0.6,
                        "metadata": {"content": duplicate.content, "reinforcements": duplicate.reinforcement_count}
                    })
                    
                mut_id = str(uuid.uuid4())
                await self.storage.store_semantic_memory(duplicate, mut_id)
                self._vector_insert_entry(duplicate)
                continue
                
            # First time Tier 2 contextual dialog
            if cand.sensitivity_tier == 2 and self.policy_engine.is_first_tier2():
                self.event_bus.emit("memory", "MEMORY_CONTEXTUAL_DIALOG", {"memory": asdict(cand)})
                # Still put it in the review queue by default for the backend
                cand.approval_state = "pending"
                mut_id = str(uuid.uuid4())
                await self.storage.store_semantic_memory(cand, mut_id)
                self._vector_insert_entry(cand)
                self.event_bus.emit("memory", "MEMORY_PENDING_REVIEW", {"memory": asdict(cand)})
                continue
                
            route = self.policy_engine.route(cand)
            mut_id = str(uuid.uuid4())
            
            if route == StorageRoute.AUTO_SAVE:
                cand.approval_state = "saved"
                await self.storage.store_semantic_memory(cand, mut_id)
                self._vector_insert_entry(cand)
                self.event_bus.emit("memory", "MEMORY_SAVED", {"memory": asdict(cand)})
                self.event_bus.emit("timeline", "create", {
                    "category": "memory",
                    "title": "Memory Auto-Saved",
                    "description": f"Persisted new memory: '{cand.content}'",
                    "source": "memory_runtime",
                    "importance": 0.5,
                    "metadata": {"content": cand.content, "why_remembered": cand.why_remembered, "category": cand.category}
                })
                logging.info(f"Memory Auto-Saved: {cand.content}")
                
            elif route == StorageRoute.REVIEW_QUEUE:
                cand.approval_state = "pending"
                await self.storage.store_semantic_memory(cand, mut_id)
                self._vector_insert_entry(cand)
                self.event_bus.emit("memory", "MEMORY_PENDING_REVIEW", {"memory": asdict(cand)})
                logging.info(f"Memory Sent to Inbox: {cand.content}")
                
            elif route == StorageRoute.CONSENT_REQUIRED:
                cand.approval_state = "pending"
                # RAM ONLY - Do not write to storage!
                self.event_bus.emit("memory", "MEMORY_SENSITIVE_CANDIDATE", {"memory": asdict(cand)})
    def form_incremental_memory(self, working_memory_dict: Dict[str, Any]) -> None:
        """
        Continuous Memory Formation (`HYP-05`).
        Called by WorkingMemoryRuntime whenever active files, terminal errors, or objectives shift meaningfully.
        Appends episodic shift events and extracts incremental factual context without waiting for user chat turns.
        """
        active_files = working_memory_dict.get("active_files", [])
        errors = working_memory_dict.get("unresolved_errors", [])
        repo = working_memory_dict.get("current_repository")
        
        shift_summary = f"Working state shift in {repo or 'Unknown Project'} ({len(active_files)} active files, {len(errors)} unresolved errors)"
        logging.info(f"MemoryRuntime.form_incremental_memory: {shift_summary}")
        
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.storage.append_episodic_event(
                event_id=str(uuid.uuid4()),
                event_type="CONTINUOUS_WORKING_MEMORY_SHIFT",
                turn_id=None,
                payload=working_memory_dict
            ), self._loop)

    async def recall_context(self) -> str:
        """
        Retrieves relevant semantic memories to inject into the system prompt.
        """
        memories = await self.storage.get_all_semantic_memory()
        if not memories:
            return ""
            
        lines = ["User Preferences & Known Facts:"]
        for m in memories:
            if m.approval_state in ["saved", "session_only"]:
                lines.append(f"- {m.content}")
                
        for m in self.session_only_memories:
            lines.append(f"- {m.content}")
            
        return "\n".join(lines)

    async def recall_ghosts_for_transcript(self, transcript: str):
        """
        Evaluates semantic memories against the current transcript.
        Applies confidence gating, temporal cooldowns, and semantic cluster suppression.
        """
        if not hasattr(self, "_last_surfaced_memories") or self._last_surfaced_memories is None:
            self._last_surfaced_memories = {}

        memories = await self.storage.get_all_semantic_memory()
        if not memories:
            return
            
        now = time.time()
        words = set(transcript.lower().split())
        
        for m in memories:
            cluster_id = getattr(m, 'semantic_cluster_id', f"cluster_{len(m.content)}")
            mem_key = getattr(m, 'id', None) or m.content
            
            # Simple cooldown check (don't surface the same memory or cluster within 10 minutes / 600s)
            last_surfaced = self._last_surfaced_memories.get(mem_key, 0)
            if now - last_surfaced < 600:
                continue
                
            mem_words = set(m.content.lower().split())
            intersection = words.intersection(mem_words)
            meaningful = [w for w in intersection if len(w) > 4]
            
            if not meaningful:
                continue
                
            confidence = len(meaningful) / max(1, len(mem_words))
            
            # Strict Gating: surface only high confidence matches
            if confidence > 0.4:
                self._last_surfaced_memories[mem_key] = now
                logger.info(f"MemoryRuntime: Surfacing ghost [Conf {confidence:.2f}] for '{m.content}'")
                
                self.event_bus.emit("memory", "MEMORY_RECALLED", {
                    "summary": m.content,
                    "confidence": confidence,
                    "cluster_id": cluster_id,
                    "semantic_type": "MEMORY_RECALLED",
                    "source": "memory_runtime"
                })
                break # Only surface the single highest confidence match per turn
    def _vector_insert_entry(self, entry):
        if not getattr(self, 'vector_store', None):
            return
        try:
            from arova.core.cognition.memory.schema import VectorMemory, MemoryMetadata
            import time
            meta = MemoryMetadata(
                semantic_type=entry.type or "fact",
                source_context=entry.category or "general",
                confidence=float(getattr(entry, 'confidence', 0.8)),
                attention_weight=float(getattr(entry, 'continuity_value', 0.5)),
                retrieval_frequency=int(getattr(entry, 'reinforcement_count', 0)),
                last_retrieved=getattr(entry, 'last_reinforced_at', None)
            )
            vm = VectorMemory(
                id=entry.id,
                content=entry.content,
                metadata=meta,
                timestamp=float(getattr(entry, 'created_at', time.time()))
            )
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, self.vector_store.insert, vm)
            except RuntimeError:
                # If no loop is running, run synchronously
                self.vector_store.insert(vm)
        except Exception as e:
            import logging
            logging.debug(f"Vector insert failed (non-fatal): {e}")
