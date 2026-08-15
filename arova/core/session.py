import os
import json
import uuid
import time
from pathlib import Path
from typing import Any, List, Dict, Optional
from dataclasses import dataclass, field, asdict

from arova.core.time import RuntimeClock

@dataclass
class ConversationTurn:
    """Represents a single conversational turn (user input + assistant response) in the active memory."""
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_transcript: str = ""
    user_audio_ref: Optional[str] = None
    timestamp_start: float = field(default_factory=RuntimeClock.now)
    timestamp_end: float = 0.0
    
    # Semantic processing
    intent_type: Optional[str] = None
    intent_confidence: float = 0.0
    
    # Execution & Response
    associated_plan_id: Optional[str] = None
    assistant_response: str = ""
    interrupted: bool = False

class ConversationSession:
    """
    Stateful conversational memory with Temporal Tiers: Active, Warm, Cold.
    """
    
    def __init__(self, system_prompt: str | None = None, state_store: Any | None = None):
        self._system_prompt = system_prompt.strip() if system_prompt else None
        
        # Temporal Memory Tiers
        self._active_turn: Optional[ConversationTurn] = None
        self._warm_context: List[ConversationTurn] = []
        self._cold_messages: List[Dict[str, Any]] = [] # Archived simple messages for persistence
        
        self._revision = 0
        self._state_store = state_store
        
        self._active_plan_id: str | None = None
        self._active_plan_timestamp: float = 0.0
        self._authoritative_turn_id: Optional[str] = None
        
        # Rigid duplicate prevention guard
        self._last_user_text: str = ""
        self._last_user_ts: float = 0.0
        
        # Memory extraction cooldown (prevent spam)
        self._last_memory_extract_ts: float = 0.0
        self._persistent_last_active_ts: float = 0.0
        
        # Phase 3: Persistent Cognitive Threads overlay
        from arova.core.intention.threads import ThreadManager
        self.thread_manager = ThreadManager(self)
        
        # We still expose a legacy _messages array for the current UI to function during migration
        self._legacy_messages: List[Dict[str, Any]] = []
        
    def _is_duplicate_user_msg(self, text: str) -> bool:
        """Rigid duplicate prevention: reject identical user text within 5 seconds."""
        now = time.time()
        if text == self._last_user_text and (now - self._last_user_ts) < 5.0:
            return True
        return False
    
    def start_new_turn(self, user_transcript: str) -> ConversationTurn:
        """Finalizes any active turn and starts a new one."""
        # Rigid dedup: reject identical user messages within 5s
        if self._is_duplicate_user_msg(user_transcript):
            return self._active_turn or ConversationTurn(user_transcript=user_transcript)
            
        if self._active_turn:
            self._active_turn.timestamp_end = RuntimeClock.now()
            self._warm_context.append(self._active_turn)
            # Prune warm context -> cold storage if needed (e.g. > 10 turns)
            if len(self._warm_context) > 10:
                old_turn = self._warm_context.pop(0)
                self._archive_turn(old_turn)
                
        self._active_turn = ConversationTurn(user_transcript=user_transcript)
        self._authoritative_turn_id = self._active_turn.turn_id
        
        # Update dedup guard
        self._last_user_text = user_transcript
        self._last_user_ts = time.time()
        
        # Update legacy format for UI
        self._legacy_messages.append({
            "id": self._active_turn.turn_id,
            "role": "user", 
            "content": user_transcript, 
            "timestamp": time.time()
        })
        self._revision += 1
        return self._active_turn

    def update_active_user_transcript(self, transcript: str):
        """Updates the user_transcript for the active authoritative turn."""
        if self._active_turn:
            self._active_turn.user_transcript = transcript
            self._last_user_text = transcript
            for msg in reversed(self._legacy_messages):
                if msg.get("id") == self._active_turn.turn_id and msg.get("role") == "user":
                    msg["content"] = transcript
                    break
            self._revision += 1

    def get_previous_user_turn_timestamp(self) -> float | None:
        """Returns the timestamp of the previous user turn before the current active turn for absence gap calculation."""
        active_id = self._active_turn.turn_id if self._active_turn else None
        for msg in reversed(self._legacy_messages):
            if msg.get("role") == "user" and msg.get("id") != active_id:
                ts = msg.get("timestamp")
                if ts and ts > 0:
                    return ts
        return self._persistent_last_active_ts if self._persistent_last_active_ts > 0 else None
        
    def get_authoritative_turn_id(self) -> Optional[str]:
        return self._authoritative_turn_id
        
    def is_authoritative(self, turn_id: Optional[str]) -> bool:
        if not turn_id or not self._authoritative_turn_id:
            return False
        return turn_id == self._authoritative_turn_id
        
    def invalidate_turn(self):
        """Immediately strips the current turn of its authority (e.g. on interruption)."""
        self._authoritative_turn_id = None
        
    def end_active_turn(self, response: str, interrupted: bool = False):
        if self._active_turn:
            self._active_turn.assistant_response = response
            self._active_turn.interrupted = interrupted
            self._active_turn.timestamp_end = RuntimeClock.now()
            
            import uuid
            msg_id = f"asst_{self._active_turn.turn_id}"
            
            # Check if this turn already has an assistant response in legacy_messages
            has_existing = any(m.get("id", "").startswith(msg_id) for m in self._legacy_messages)
            if has_existing:
                msg_id = f"{msg_id}_{str(uuid.uuid4())[:8]}"

            # Update legacy format
            self._legacy_messages.append({
                "id": msg_id,
                "role": "assistant", 
                "content": response, 
                "timestamp": time.time()
            })
            self._revision += 1
            self._save_history()
            
            # Eagerly extract memories Phase 7.5 — with 60-second cooldown to prevent spam
            # Skip extraction on error/fallback responses (waste of tokens)
            _error_markers = ["unable to reach llm", "unable to connect", "no inference provider",
                              "encountered an unexpected error", "max retries exceeded"]
            _is_error_response = any(em in response.lower() for em in _error_markers)
            if hasattr(self, "_memory_runtime") and self._memory_runtime and not _is_error_response:
                import asyncio
                import logging
                now = time.time()
                if (now - self._last_memory_extract_ts) >= 60.0:
                    loop = getattr(self._memory_runtime, "_loop", None)
                    if loop:
                        self._last_memory_extract_ts = now
                        logging.info(f"Session: Scheduling extract_eagerly for turn {self._active_turn.turn_id}")
                        asyncio.run_coroutine_threadsafe(self._memory_runtime.extract_eagerly(self._active_turn), loop)
                    else:
                        logging.error("Session: _memory_runtime._loop is None, cannot schedule extract_eagerly")
                else:
                    logging.debug(f"Session: Skipping extract_eagerly (cooldown: {60.0 - (now - self._last_memory_extract_ts):.0f}s remaining)")

    def get_canonical_history(self) -> List[Dict[str, Any]]:
        """Returns history conforming to the canonical SessionMessage schema."""
        canonical = []
        for msg in self._legacy_messages:
            canonical.append({
                "id": msg.get("id", str(uuid.uuid4())),
                "role": msg.get("role"),
                "content": msg.get("content"),
                "timestamp": msg.get("timestamp", time.time())
            })
        return canonical
            
    def get_active_turn(self) -> Optional[ConversationTurn]:
        return self._active_turn
        
    def _archive_turn(self, turn: ConversationTurn):
        self._cold_messages.append({"role": "user", "content": turn.user_transcript})
        if turn.assistant_response:
            self._cold_messages.append({"role": "assistant", "content": turn.assistant_response})
            
        # Delegate to formal MemoryRuntime if attached
        if hasattr(self, "_memory_runtime") and self._memory_runtime:
            import asyncio
            loop = getattr(self._memory_runtime, "_loop", None)
            if loop:
                asyncio.run_coroutine_threadsafe(self._memory_runtime.archive_turn(turn), loop)
                
        self._save_history()
        
    def set_active_plan(self, plan_id: str | None):
        self._active_plan_id = plan_id
        self._active_plan_timestamp = time.time() if plan_id else 0.0
        if self._active_turn and plan_id:
            self._active_turn.associated_plan_id = plan_id
            
    def get_active_plan_id(self) -> str | None:
        return self._active_plan_id
        
    def get_active_plan_timestamp(self) -> float:
        return self._active_plan_timestamp

    def get_revision(self) -> int:
        return self._revision
        
    def set_system_prompt(self, prompt: str | None) -> None:
        new_prompt = prompt.strip() if prompt else None
        if self._system_prompt != new_prompt:
            self._system_prompt = new_prompt
            self._revision += 1
        
    # --- Legacy Adaptors for current UI/LLM pipelines ---
    
    def add_user_message(self, content: str) -> bool:
        if not content.strip(): return False
        
        # Rigid dedup: reject identical user messages within 5s
        if self._is_duplicate_user_msg(content):
            return True
            
        self.start_new_turn(content)
        self._save_history()
        return True
        
    def add_assistant_message(self, content: str) -> bool:
        if not content.strip(): return False
        self.end_active_turn(content)
        return True

    def clear(self, keep_system_prompt: bool = True) -> None:
        self._active_turn = None
        self._warm_context.clear()
        self._cold_messages.clear()
        
        changed = len(self._legacy_messages) > 0
        self._legacy_messages.clear()
        
        if not keep_system_prompt and self._system_prompt is not None:
            self._system_prompt = None
            changed = True
        
        if changed:
            self._revision += 1
            self._save_history()

    def get_messages(self) -> list[dict[str, str]]:
        return [dict(m) for m in self._legacy_messages]
        
    def build_api_messages(self, max_turns: int = 4) -> list[dict[str, str]]:
        """
        Builds the context window for the LLM. 
        Implements a sliding window that favors recency and caps historical message bloat.
        """
        api_msgs = []
        if self._system_prompt:
            api_msgs.append({"role": "system", "content": self._system_prompt[:1000]})
            
        recent_messages = self._legacy_messages[-max_turns:] if len(self._legacy_messages) > max_turns else self._legacy_messages
        
        last_idx = len(recent_messages) - 1
        for idx, m in enumerate(recent_messages):
            role = m.get("role", "user")
            content = str(m.get("content", ""))
            # Never truncate the active user prompt (last item), but truncate past turns to 800 chars max
            if idx < last_idx and len(content) > 800:
                content = content[:800] + "... [historical context truncated]"
            api_msgs.append({"role": role, "content": content})
            
        return api_msgs

    def last_assistant_message(self) -> str | None:
        for m in reversed(self._legacy_messages):
            if m["role"] == "assistant":
                return m["content"]
        return None

    def message_count(self) -> int:
        return len(self._legacy_messages)

    def _load_history(self) -> None:
        pass

    def _save_history(self) -> None:
        if hasattr(self, '_persist_callback') and self._persist_callback:
            try:
                self._persist_callback()
            except Exception as e:
                logging.error(f"Failed to persist session history: {e}")
        
    def to_dict(self) -> dict:
        return {
            "system_prompt": self._system_prompt,
            "legacy_messages": self._legacy_messages,
            "persistent_last_active_ts": self._persistent_last_active_ts or time.time()
        }
        
    @classmethod
    def from_dict(cls, data: dict, state_store=None) -> 'ConversationSession':
        session = cls(system_prompt=data.get("system_prompt"), state_store=state_store)
        session._legacy_messages = data.get("legacy_messages", [])
        session._persistent_last_active_ts = data.get("persistent_last_active_ts", 0.0)
        return session

    def get_plans(self) -> list:
        from arova.core.plan_store import get_plans
        return get_plans()

    def add_plan(self, plan_data: dict) -> dict:
        from arova.core.plan_store import save_plan
        return save_plan(plan_data)

    def delete_plan(self, plan_id: str) -> bool:
        from arova.core.plan_store import delete_plan
        return delete_plan(plan_id)
