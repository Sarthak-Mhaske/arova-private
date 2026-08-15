import time
import uuid
import logging
from typing import Optional

class RuntimeEventMapper:
    @staticmethod
    def _base_event(event_type: str, source: str = "bridge") -> dict:
        return {
            "v": 1,
            "type": event_type,
            "id": f"evt_{uuid.uuid4().hex[:12]}",
            "timestamp": int(time.time() * 1000),
            "source": source
        }

    @classmethod
    def map_internal_event(cls, internal_type: str, payload: dict, topic: str = "") -> Optional[dict]:
        """
        Maps an internal EventBus event to the stable external WebSocket protocol.
        Returns the external event dictionary, or None if the event shouldn't be broadcast.
        """
        logger = logging.getLogger("Arova.Bridge")
        event = None
        
        # Unbox DictPayload's nested 'data' if present
        if "data" in payload and isinstance(payload["data"], dict):
            payload = payload["data"]
        
        if internal_type == "COGNITION_STATE_CHANGED":
            event = cls._base_event("orb.state", "cognition_runtime")
            internal_state = payload.get("state", "idle")
            # Map internal verbose states to canonical frontend orb states
            state_map = {
                "GENERATING_RESPONSE": "streaming",
                "LISTENING": "listening",
                "THINKING": "thinking",
                "PLANNING": "thinking",
                "ANALYZING_INTENT": "thinking",
                "CLASSIFYING_INTENT": "thinking",
                "DEEP_PLANNING_REQUIRED": "thinking",
                "STANDARD_ROUTING": "thinking",
                "PLANNING_ACTION": "thinking",
                "EXECUTING_FAST_PATH": "executing",
                "EXECUTING_ACTION": "executing",
                "EXECUTING": "executing",
                "REFLECTING": "reflecting",
                "ERROR": "error",
                "dormant": "idle"
            }
            event["state"] = state_map.get(internal_state, "idle")
            event["details"] = payload.get("details", "")
            event["raw_state"] = internal_state

        elif internal_type == "TRANSCRIPT_FINAL":
            event = cls._base_event("voice.transcript", "voice_runtime")
            event["text"] = payload.get("transcript", "")
            event["transcript"] = payload.get("transcript", "")
        elif internal_type == "TEXT_STREAM_STARTED":
            event = cls._base_event("stream.start", "cognition_runtime")
            event["stream_id"] = f"asst_{payload.get('turn_id', 'default')}"
        elif internal_type == "TTS_STARTED":
            event = cls._base_event("voice.speaker_state", "voice_runtime")
            event["speaking"] = True
        elif internal_type in ("TTS_COMPLETED", "TTS_INTERRUPTED"):
            event = cls._base_event("voice.speaker_state", "voice_runtime")
            event["speaking"] = False

        elif internal_type == "TEXT_CHUNK_GENERATED":
            event = cls._base_event("stream.delta", "cognition_runtime")
            event["stream_id"] = f"asst_{payload.get('turn_id', 'default')}"
            event["delta"] = payload.get("text", "")
            event["seq"] = payload.get("seq", 0)

        elif internal_type == "NODE_STATE_CHANGED":
            event = cls._base_event("automation.action_progress", "automation_runtime")
            event["action"] = payload.get("action")
            event["node_state"] = payload.get("state")

        elif internal_type == "TEXT_RESPONSE_GENERATED":
            event = cls._base_event("stream.end", "cognition_runtime")
            event["stream_id"] = f"asst_{payload.get('turn_id', 'default')}"
            
        elif internal_type == "PROVIDER_FALLBACK":
            event = cls._base_event("provider.fallback", "capability_router")
            event.update(payload)
            
        elif internal_type == "PROVIDER_CHANGED":
            event = cls._base_event("provider.changed", "capability_router")
            event.update(payload)
            
        elif internal_type == "PROVIDER_RECOVERED":
            event = cls._base_event("provider.recovered", "capability_router")
            event.update(payload)
            event["stream_id"] = payload.get("turn_id", "default")

        elif internal_type == "STREAM_INTERRUPTED":
            event = cls._base_event("stream.interrupted", "cognition_runtime")
            event["stream_id"] = payload.get("turn_id", "default")

        elif internal_type == "ATTENTION_STATE_CHANGED":
            event = cls._base_event("awareness.update", "ambient_observer")
            event["key"] = "focus"
            event["value"] = payload.get("focus", "")

        elif internal_type == "CONTEXT_CHANGED":
            event = cls._base_event("awareness.ambient_snapshot", "ambient_observer")
            snapshot = payload.get("snapshot", {}) if isinstance(payload.get("snapshot"), dict) else payload
            event["active_app"] = snapshot.get("active_app")
            event["window_title"] = snapshot.get("window_title")
            event["workspace"] = snapshot.get("workspace")
            event["is_idle"] = snapshot.get("is_idle", False)
            event["time_of_day"] = snapshot.get("time_of_day", "")
            event["open_windows"] = snapshot.get("open_windows", [])
            event["playing_media"] = snapshot.get("playing_media", [])
            event["attention_narrative"] = payload.get("attention_narrative", snapshot.get("attention_narrative", ""))

        elif internal_type == "MEMORY_RECALLED":
            event = cls._base_event("memory.ghost", "memory_runtime")
            event["text"] = payload.get("summary", "")
            event["age"] = payload.get("age", "recent")
            
        elif internal_type == "PRESENCE_PROFILE_UPDATED":
            event = cls._base_event("cognition.modulation", "presence_modulator")
            event["profile"] = {
                "verbosity": payload.get("verbosity"),
                "cadence": payload.get("cadence"),
                "emotional_temperature": payload.get("emotional_temperature"),
                "ambient_density": payload.get("ambient_density")
            }
            
        elif internal_type == "THREAD_SYNC":
            event = cls._base_event("thread.sync", "thread_manager")
            event["threads"] = payload.get("threads", [])
            
        elif internal_type == "TIMELINE_EVENT":
            event = cls._base_event("TIMELINE_EVENT", "timeline_store")
            event["event"] = payload.get("event", payload)
            
        elif internal_type == "PROJECTION_UPDATED":
            event = cls._base_event("projection.updated", "runtime_projector")
            event["projection"] = payload

        elif internal_type == "EVENT_INGESTED" and topic == "capture":
            event = cls._base_event("capture.event_ingested", "activity_capture")
            event["event"] = payload

        elif internal_type == "sync" and topic == "workspace":
            event = cls._base_event("workspace.sync", "workspace_manager")
            event["active_workspace_id"] = payload.get("active_workspace_id")
            event["active_workspace"] = payload.get("active_workspace")
            event["workspaces"] = payload.get("workspaces", [])

        elif internal_type == "WORKING_MEMORY_CHANGED":
            event = cls._base_event("working_memory.changed", "working_memory_runtime")
            event["state"] = payload

        elif internal_type == "REASONING_STEP_COMPLETED":
            event = cls._base_event("reasoning.step_completed", "reasoning_runtime")
            event["outcome"] = payload

        elif internal_type == "MEMORY_SAVED":
            event = cls._base_event("memory.saved", "memory_runtime")
            event["memory"] = payload.get("memory", {})
            
        elif internal_type == "MEMORY_PENDING_REVIEW":
            event = cls._base_event("memory.pending_review", "memory_runtime")
            event["memory"] = payload.get("memory", {})
            
        elif internal_type == "MEMORY_SENSITIVE_CANDIDATE":
            event = cls._base_event("memory.sensitive_candidate", "memory_runtime")
            event["memory"] = payload.get("memory", {})
            
        elif internal_type == "MEMORY_CONTEXTUAL_DIALOG":
            event = cls._base_event("memory.contextual_dialog", "memory_runtime")
            event["memory"] = payload.get("memory", {})

        if event:
            sid_log = f" [stream_id={event.get('stream_id')}]" if 'stream_id' in event else ""
            logger.info(f"EMIT EXTERNAL EVENT: {event['type']}{sid_log} (from {internal_type})")
            
        return event
