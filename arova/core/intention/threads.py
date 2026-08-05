import time
import uuid
from typing import Dict, List, Literal, Optional, Any
from dataclasses import dataclass, field
from arova.core.cognition.provenance import ProvenanceSource

ThreadState = Literal["foreground", "active", "ambient", "latent", "archived"]

@dataclass
class ContinuitySnapshot:
    """A compressed memory of a thread when it goes dormant."""
    summary: str = ""
    unresolved_questions: List[str] = field(default_factory=list)
    why_it_matters: str = ""
    active_pressures: float = 0.0
    provenance: List[ProvenanceSource] = field(default_factory=list)
    emotional_temperature: str = "neutral"
    environment_context: Dict[str, str] = field(default_factory=dict)
    temporal_horizon: str = "recent"
    continuity_entropy: float = 0.0
    timestamp: float = field(default_factory=time.time)

@dataclass
class CognitiveThread:
    """
    A semantic continuity overlay. Stores the semantic identity, conversation history,
    and temporal state of an ongoing conversational/cognitive thread.
    """
    thread_id: str = field(default_factory=lambda: f"thr_{uuid.uuid4().hex[:12]}")
    title: str = "New Thread"
    state: ThreadState = "foreground"
    pinned: bool = False
    messages: List[Dict[str, Any]] = field(default_factory=list)
    
    # Associated chronological turn IDs and their affinity [-1.0, 1.0]
    thread_affinity: Dict[str, float] = field(default_factory=dict)
    
    # Thread Graph Linking
    related_thread_ids: List[str] = field(default_factory=list)
    semantic_distance: Dict[str, float] = field(default_factory=dict)
    
    # Continuity & Resonance
    continuity_resonance: float = 0.0 # Spikes when context matches this dormant thread
    continuity_snapshot: Optional[ContinuitySnapshot] = None
    
    # Fatigue Dimensions
    surface_fatigue: float = 0.0
    interrupt_fatigue: float = 0.0
    emotional_fatigue: float = 0.0
    semantic_fatigue: float = 0.0
    
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    @property
    def turn_ids(self) -> List[str]:
        return list(self.thread_affinity.keys())

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        d = asdict(self)
        # Snapshot needs manual serialization if present
        if self.continuity_snapshot:
            snap_dict = asdict(self.continuity_snapshot)
            snap_dict['provenance'] = [p.to_dict() for p in self.continuity_snapshot.provenance]
            d["continuity_snapshot"] = snap_dict
        return d
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CognitiveThread':
        snap_data = data.pop("continuity_snapshot", None)
        thread = cls(**data)
        if snap_data:
            thread.continuity_snapshot = ContinuitySnapshot(**snap_data)
        return thread

class ThreadManager:
    """
    Manages the lifecycle and state of CognitiveThreads. 
    Periodically resynthesizes summaries and calculates resonance.
    """
    def __init__(self, session_manager, event_bus=None):
        self._threads: Dict[str, CognitiveThread] = {}
        self.session_manager = session_manager
        self.event_bus = event_bus

        if self.event_bus:
            self.event_bus.subscribe("intention", "THREAD_ACTION_REQUESTED", self._handle_action_request)
            
    def _handle_action_request(self, event):
        payload = event.data if hasattr(event, "data") else event
        action = payload.get("action")
        thread_id = payload.get("thread_id")
        
        if not thread_id or not action:
            return
            
        if action == "resume": self.resume_thread(thread_id)
        elif action == "pause": self.pause_thread(thread_id)
        elif action == "archive": self.archive_thread(thread_id)
        elif action == "delete": self.delete_thread(thread_id)
        elif action == "pin": self.toggle_pin_thread(thread_id)
        elif action == "rename":
            self.rename_thread(thread_id, payload.get("payload", {}).get("new_title", "Renamed Thread"))
        
    def _evaluate_decay(self, thread: CognitiveThread):
        """Archives dormant threads if they have zero pressure and zero resonance."""
        if thread.state in ("latent", "ambient") and not thread.pinned:
            if thread.continuity_resonance == 0.0:
                pressures = thread.continuity_snapshot.active_pressures if thread.continuity_snapshot else 0.0
                if pressures == 0.0:
                    thread.state = "archived"
                    thread.last_updated = time.time()

    def _sync(self):
        if self.event_bus:
            # Emit full state of threads to frontend
            threads_data = []
            for t in self._threads.values():
                self._evaluate_decay(t)
                snap = t.continuity_snapshot
                threads_data.append({
                    "thread_id": t.thread_id,
                    "title": t.title,
                    "state": t.state,
                    "pinned": t.pinned,
                    "messages": t.messages,
                    "resonance": t.continuity_resonance,
                    "active_pressures": snap.active_pressures if snap else 0.0,
                    "last_updated": t.last_updated,
                    "summary": snap.summary if snap else "",
                    "unresolved_questions": snap.unresolved_questions if snap else [],
                    "why_it_matters": snap.why_it_matters if snap else ""
                })
            self.event_bus.emit("cognition", "THREAD_SYNC", {"threads": threads_data})
        
    def create_thread(self, title: str, initial_turn_id: Optional[str] = None) -> CognitiveThread:
        thread = CognitiveThread(title=title)
        if initial_turn_id:
            thread.thread_affinity[initial_turn_id] = 1.0
        self._threads[thread.thread_id] = thread
        self._sync()
        return thread
        
    def get_thread(self, thread_id: str) -> Optional[CognitiveThread]:
        return self._threads.get(thread_id)
        
    def update_thread_state(self, thread_id: str, new_state: ThreadState):
        thread = self.get_thread(thread_id)
        if thread:
            # If moving to dormant (latent/archived) from active, take a snapshot
            if new_state in ("latent", "archived") and thread.state in ("foreground", "active", "ambient"):
                self._take_snapshot(thread)
            thread.state = new_state
            thread.last_updated = time.time()
            self._sync()
            
    # Phase 7A: Explicit Thread Actions
    def resume_thread(self, thread_id: str):
        thread = self.get_thread(thread_id)
        if thread:
            # Save current foreground thread messages if any
            if hasattr(self.session_manager, "_legacy_messages") and self.session_manager._legacy_messages:
                fg_threads = [t for t in self._threads.values() if t.state == "foreground" and t.thread_id != thread_id]
                if fg_threads:
                    fg_threads[0].messages = list(self.session_manager._legacy_messages)
                    fg_threads[0].state = "latent"

            # Set selected thread to foreground and populate session messages
            self.update_thread_state(thread_id, "foreground")
            if hasattr(self.session_manager, "_legacy_messages"):
                self.session_manager._legacy_messages = list(thread.messages)
        
    def pause_thread(self, thread_id: str):
        self.update_thread_state(thread_id, "latent")
        
    def archive_thread(self, thread_id: str):
        self.update_thread_state(thread_id, "archived")
        
    def delete_thread(self, thread_id: str):
        if thread_id in self._threads:
            thread = self._threads[thread_id]
            
            # Check if this thread is currently loaded into the active session
            if self.session_manager and getattr(self.session_manager, "_legacy_messages", None):
                active_msgs = self.session_manager._legacy_messages
                if active_msgs and thread.messages:
                    if active_msgs[0].get("id") == thread.messages[0].get("id"):
                        # Clear active session state to prevent the deleted thread from resurrecting
                        self.session_manager._legacy_messages = []
                        if hasattr(self.session_manager, "_warm_context"):
                            self.session_manager._warm_context = []
                        if hasattr(self.session_manager, "_active_turn"):
                            self.session_manager._active_turn = None
            
            del self._threads[thread_id]
            self._sync()
        
    def rename_thread(self, thread_id: str, new_title: str):
        thread = self.get_thread(thread_id)
        if thread:
            thread.title = new_title
            thread.last_updated = time.time()
            self._sync()
            
    def toggle_pin_thread(self, thread_id: str) -> bool:
        thread = self.get_thread(thread_id)
        if thread:
            thread.pinned = not thread.pinned
            thread.last_updated = time.time()
            self._sync()
            return thread.pinned
        return False
            
    def link_turn_to_thread(self, thread_id: str, turn_id: str, affinity: float = 1.0):
        thread = self.get_thread(thread_id)
        if thread:
            # Accumulate affinity up to bounds [-1.0, 1.0]
            current_affinity = thread.thread_affinity.get(turn_id, 0.0)
            new_affinity = max(-1.0, min(1.0, current_affinity + affinity))
            thread.thread_affinity[turn_id] = new_affinity
            thread.last_updated = time.time()
            
    def _take_snapshot(self, thread: CognitiveThread):
        """Take a snapshot of the thread's cognitive state before it goes dormant."""
        msg_count = len(thread.messages)
        user_msgs = [m for m in thread.messages if m.get("role") == "user"]
        
        turn_count = max(len(thread.turn_ids), len(user_msgs), 1 if msg_count > 0 else 0)
        
        first_user_text = user_msgs[0].get("content", "").strip() if user_msgs else ""
        last_user_text = user_msgs[-1].get("content", "").strip() if user_msgs else ""
        
        if first_user_text:
            if len(first_user_text) < 25:
                summary_text = f"Query: \"{first_user_text}\""
            elif len(first_user_text) > 60:
                summary_text = f"Discussion on: {first_user_text[:60]}..."
            else:
                summary_text = f"Discussion on: {first_user_text}"
        else:
            summary_text = f"Conversation Thread '{thread.title}'"

        questions = []
        for m in reversed(user_msgs):
            content = m.get("content", "").strip()
            if "?" in content:
                questions.append(content)
        
        if questions:
            unresolved = questions[:3]
        elif last_user_text:
            unresolved = [f"Continue query: \"{last_user_text[:50]}\""]
        else:
            unresolved = [f"Resume work on {thread.title}"]

        if turn_count > 1:
            why_it_matters = f"Preserves contextual history across {turn_count} turns for {thread.title}."
        elif turn_count == 1:
            why_it_matters = f"Preserves prompt context for quick continuation."
        else:
            why_it_matters = f"Maintains thread state for future interaction."

        workspace_title = "Active Workspace"
        if hasattr(self.session_manager, "runtime") and getattr(self.session_manager.runtime, "workspace_manager", None):
            active_ws = self.session_manager.runtime.workspace_manager.get_active_workspace()
            if active_ws:
                workspace_title = active_ws.title

        thread.continuity_snapshot = ContinuitySnapshot(
            summary=summary_text,
            unresolved_questions=unresolved,
            why_it_matters=why_it_matters,
            active_pressures=min(1.0, 0.3 + (turn_count * 0.1)),
            environment_context={"workspace": workspace_title, "turn_count": str(turn_count)}
        )
        
    def get_threads_by_state(self, state: ThreadState) -> List[CognitiveThread]:
        return [t for t in self._threads.values() if t.state == state]
        
    def get_all_threads(self) -> List[CognitiveThread]:
        return list(self._threads.values())
