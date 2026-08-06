import logging
from typing import Optional
from arova.core.events import RuntimeEventBus
from arova.core.session import ConversationSession
from arova.core.config.loader import load_config
from arova.core.logger import execution_logger
from arova.core.state import RuntimeProjectionCache
from arova.core.api import RuntimeFacade
from arova.core.capabilities.registry import CapabilityRegistry
from arova.core.capabilities.runtime import CapabilityRuntime
from arova.core.capabilities.builtins import register_builtins
from arova.core.platform.system.executor import SystemExecutionLayer
from arova.core.memory.runtime import MemoryRuntime
from arova.core.policy.runtime import PolicyRuntime
from arova.core.automation.runtime import AutomationRuntime
from arova.core.models.orchestrator import ModelOrchestrator
from arova.core.models.profiles import CognitiveProfile
# TIER 0.3: Voice/Ambience imports are LAZY inside gated blocks to avoid hard deps in minimal beta
# (numpy, pyaudio, etc. not required for Capture→Workspace→Restore→Chat)

# Environment Perception (Phase 10)
from arova.core.platform.windowing.manager import WindowingManager
from arova.core.environment.workspace_semantics import WorkspaceSemanticAnalyzer
from arova.core.environment.workspace import WorkspaceAwarenessEngine
from arova.core.environment.attention import AttentionGraphEngine
from arova.core.environment.session import SessionManager
from arova.core.environment.intent import AmbientIntentDetector
from arova.core.environment.graph import SemanticEnvironmentGraph
from arova.core.cognition.trace import CognitiveTraceEngine
from arova.core.cognition.memory_retrieval import MemoryRetrievalEngine
from arova.core.cognition.context import ContextSynthesizer
from arova.core.cognition.router import CognitiveRouter
from arova.core.cognition.planner import CognitivePlanner
from arova.core.cognition.priority import CognitivePriorityEngine, CognitiveSignal
from arova.core.cognition.modulation import PresenceModulator
from arova.core.environment.trajectory import AttentionNarrativeGenerator
from arova.core.intention.graph import IntentGraph
from arova.core.intention.continuity import PlanningContinuityEngine

class RuntimeContainer:
    """
    Root dependency container for the HyprVoice runtime.
    Initializes and holds references to the EventBus, ThreadPools, Loggers, and Core Services.
    Prevents scattered global instantiation.
    """
    def __init__(self):
        self.config = load_config()
        # === TIER 0.3: Beta minimal gate — only Capture→Workspace→Restore→Chat ===
        beta_cfg = self.config.get("beta", {})
        is_beta_minimal = beta_cfg.get("profile", "minimal") == "minimal"
        # In minimal, voice/presence/ambience are OFF by default even if config says True
        self.enable_voice = (not is_beta_minimal) and beta_cfg.get("enable_voice", True)
        self.enable_presence = (not is_beta_minimal) and beta_cfg.get("enable_presence", True)
        self.enable_ambience = (not is_beta_minimal) and beta_cfg.get("enable_ambience", True)
        self.enable_warmup = (not is_beta_minimal) and beta_cfg.get("enable_warmup", True)
        self.beta_mode = "minimal" if is_beta_minimal else "full"
        logging.info(f"RuntimeContainer: BETA_{self.beta_mode.upper()} mode (voice={self.enable_voice}, presence={self.enable_presence}, ambience={self.enable_ambience})")
        self.event_bus = RuntimeEventBus()
        
        # Privacy & Trust Engine (Phase 10A)
        from arova.core.config.awareness import AwarenessManager
        self.awareness_manager = AwarenessManager()
        
        # Context Providers (Phase 10B)
        from arova.core.cognition.providers.manager import ProviderManager
        self.provider_manager = ProviderManager(self.awareness_manager)
        
        # Persistence Layer (Phase 5A)
        from arova.core.persistence.store import RuntimeStore
        self.runtime_store = RuntimeStore()
        self.runtime_snapshot = self.runtime_store.hydrate()
        
        # Cognitive Timeline (Phase 8.5)
        from arova.core.timeline.store import TimelineStore
        self.timeline = TimelineStore(event_bus=self.event_bus)

        
        # Crash Recovery
        if self.runtime_snapshot.recovery_checkpoint and not self.runtime_snapshot.recovery_checkpoint.recovered:
            # Emit a signal that we recovered from a crash, allowing UI or IntentRuntime to say "I was interrupted"
            if self.runtime_snapshot.recovery_checkpoint.interrupted_stream:
                logging.warning(f"Recovered from crash during turn: {self.runtime_snapshot.recovery_checkpoint.interrupted_stream}")
                self.event_bus.emit("cognition", "INTERRUPTED_STREAM_RECOVERED", {
                    "transcript": self.runtime_snapshot.recovery_checkpoint.interrupted_stream
                })
            self.runtime_snapshot.recovery_checkpoint.recovered = True
            self.runtime_store.save(self.runtime_snapshot)
        
        from arova.core.threads import ThreadManager
        self.thread_manager = ThreadManager()
        
        # Workspace Manager (Phase 11 Long-Lived Workspaces)
        from arova.core.cognition.workspace_manager import WorkspaceManager
        self.workspace_manager = WorkspaceManager(event_bus=self.event_bus, orchestrator=None)
        if hasattr(self.runtime_snapshot.hot_state, 'workspaces') and self.runtime_snapshot.hot_state.workspaces:
            from arova.core.cognition.workspace import CognitiveWorkspace
            for wid, w_dict in self.runtime_snapshot.hot_state.workspaces.items():
                self.workspace_manager._workspaces[wid] = CognitiveWorkspace.from_dict(w_dict)
            if self.runtime_snapshot.hot_state.active_workspace_id:
                self.workspace_manager._active_workspace_id = self.runtime_snapshot.hot_state.active_workspace_id
        
        # State and Session
        self.session = ConversationSession()
        self.session.workspace_manager = self.workspace_manager
        
        # Phase 6 Core Product Engines (`ActivityCaptureEngine`, `SearchIndex`, `KPITelemetryCollector`)
        from arova.core.cognition.search_index import SearchIndex
        from arova.core.capture.engine import ActivityCaptureEngine
        from arova.core.telemetry.kpi_metrics import KPITelemetryCollector
        self.search_index = SearchIndex()
        self.capture_engine = ActivityCaptureEngine(event_bus=self.event_bus)
        self.capture_engine.workspace_manager = self.workspace_manager
        self.capture_engine.timeline_engine = self.timeline
        self.capture_engine.subscribe(lambda evt: self.search_index.index_canonical_event(evt))
        self.workspace_manager.search_index = self.search_index

        from arova.core.memory.working_memory import WorkingMemoryRuntime
        from arova.core.reasoning.runtime import ReasoningRuntime
        from arova.core.cognition.belief import BeliefRuntime
        self.working_memory_runtime = WorkingMemoryRuntime(event_bus=self.event_bus)
        self.belief_runtime = BeliefRuntime(event_bus=self.event_bus)
        self.reasoning_runtime = ReasoningRuntime(event_bus=self.event_bus, workspace_manager=self.workspace_manager)
        self.working_memory_runtime.reasoning_runtime = self.reasoning_runtime
        self.working_memory_runtime.belief_runtime = self.belief_runtime
        self.reasoning_runtime.belief_runtime = self.belief_runtime
        self.capture_engine.working_memory_runtime = self.working_memory_runtime
        self.kpi_collector = KPITelemetryCollector(event_bus=self.event_bus)
        
        # Attach EventBus to the ThreadManager for action handling
        self.session.thread_manager.event_bus = self.event_bus
        self.event_bus.subscribe("intention", "THREAD_ACTION_REQUESTED", self.session.thread_manager._handle_action_request)
        
        # Seed threads from hot state if present
        for t_dict in self.runtime_snapshot.hot_state.active_threads:
            if isinstance(t_dict, dict):
                from arova.core.intention.threads import CognitiveThread
                self.session.thread_manager._threads[t_dict["thread_id"]] = CognitiveThread.from_dict(t_dict)
            
        # Hydrate session messages from Hot State
        for m_dict in self.runtime_snapshot.hot_state.recent_turns:
            self.session._legacy_messages.append(m_dict)
        
        # Inject Ingestion Filter — lazy import
        from arova.core.voice.turn_filter import TurnAuthorityFilter
        self.turn_filter = TurnAuthorityFilter(session=self.session)
        self.event_bus.add_filter(self.turn_filter.filter_event)
        
        # Initialize TurnCoordinator early so it processes WAKE_DETECTED before STT — lazy
        from arova.core.voice.turn_coordinator import TurnCoordinator
        self.turn_coordinator = TurnCoordinator(event_bus=self.event_bus, session=self.session)
        
        # === TIER 0.3: Voice Pipeline Runtimes (Phase 2) — GATED by beta minimal ===
        if getattr(self, "enable_voice", False):
            # Lazy imports — only needed when voice enabled (requires numpy etc.)
            from arova.core.voice.cancellation import RuntimeCancellationService
            from arova.core.voice.audio_session import AudioSessionManager
            from arova.core.voice.activity_runtime import VoiceActivityRuntime
            from arova.core.voice.wake_service import WakeRuntimeService
            from arova.core.voice.stt_service import STTRuntimeService
            from arova.core.voice.recovery_coordinator import RecoveryCoordinator, WatchdogService
            self.cancellation = RuntimeCancellationService(event_bus=self.event_bus)
            self.recovery = RecoveryCoordinator(event_bus=self.event_bus, cancellation=self.cancellation)
            self.watchdog = WatchdogService(event_bus=self.event_bus)
            
            self.audio_session = AudioSessionManager(event_bus=self.event_bus)
            self.activity_runtime = VoiceActivityRuntime(event_bus=self.event_bus)
            self.wake_service = WakeRuntimeService(event_bus=self.event_bus, config=self.config)
            
            # Wire physical mic to VAD and Wake modules
            self.audio_session.microphone.subscribe("activity_runtime", 50, self.activity_runtime.process_audio_chunk)
            self.audio_session.microphone.subscribe("wake_service", 40, self.wake_service.process_audio_chunk)
            self.wake_service.start()
            
            self.stt_service = STTRuntimeService(event_bus=self.event_bus, audio_session=self.audio_session, session=self.session)
        else:
            # BETA_MINIMAL: Voice disabled — keep attributes for graceful shutdown
            self.cancellation = None
            self.recovery = None
            self.watchdog = None
            self.audio_session = None
            self.activity_runtime = None
            self.wake_service = None
            self.stt_service = None
            logging.info("BETA_MINIMAL: Voice pipeline disabled (enable_voice=False)")
        
        self.projection_cache = RuntimeProjectionCache(event_bus=self.event_bus)
        self.facade = RuntimeFacade(event_bus=self.event_bus, projection_cache=self.projection_cache)
        
        self.capability_registry = CapabilityRegistry()
        self.system_executor = SystemExecutionLayer()
        self.capability_runtime = CapabilityRuntime(
            event_bus=self.event_bus, 
            registry=self.capability_registry,
            system_executor=self.system_executor
        )
        
        # Load legacy tools asynchronously
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(register_builtins(self.capability_registry))
        except RuntimeError:
            logging.debug("No running asyncio event loop during capability builtin registration; deferred.")

        self.memory_runtime = MemoryRuntime(event_bus=self.event_bus, config=self.config)
        if hasattr(self, 'working_memory_runtime') and self.working_memory_runtime:
            self.working_memory_runtime.memory_runtime = self.memory_runtime
        # Pass memory runtime to session to delegate archiving
        self.session._memory_runtime = self.memory_runtime
        # Wire save callback so history persists on every turn end
        self.session._persist_callback = self._persist_runtime
        
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.timeline.initialize())
            loop.create_task(self.memory_runtime.initialize())
        except RuntimeError:
            logging.debug("No running asyncio event loop during timeline/memory initialization; deferred.")
            
        self.policy_runtime = PolicyRuntime(event_bus=self.event_bus, registry=self.capability_registry)
        self.automation_runtime = AutomationRuntime(event_bus=self.event_bus)
        
        # === TIER 0.3: Ambience gated ===
        if getattr(self, "enable_ambience", False):
            from arova.core.ambience.provider import LiveOSAmbientProvider, PollingProvider
            from arova.core.ambience.observer import AmbientObserver
            self.ambient_provider = LiveOSAmbientProvider()
            self.ambient_observer = AmbientObserver(event_bus=self.event_bus, provider=self.ambient_provider, stability_window_seconds=2.0)
            self.ambient_observer.start()
        else:
            self.ambient_provider = None
            self.ambient_observer = None
            logging.info("BETA_MINIMAL: Ambience observer disabled")
        
        from arova.core.platform.windowing.manager import WindowingManager
        self.window_backend = WindowingManager.get_backend()
        
        from arova.core.cognition.providers.window_provider import WindowObserverProvider
        self.provider_manager.register(WindowObserverProvider(self.window_backend))

        # Core Pillars (Phase 12 Core Capabilities)
        from arova.core.audio.media_ducking import MediaDuckingEngine
        from arova.core.cognition.routine_tracker import RoutineTracker
        from arova.core.cognition.context_graph import ContextKnowledgeGraph
        
        self.media_ducking = MediaDuckingEngine()
        self.routine_tracker = RoutineTracker()
        self.context_graph = ContextKnowledgeGraph()

        # Wire MediaDuckingEngine to Orb & Voice states
        def _on_orb_state(payload):
            p = payload.__dict__ if hasattr(payload, '__dict__') else payload
            state_str = str(p.get("state") or p.get("data", {}).get("state") or "").lower()
            if any(s in state_str for s in ["thinking", "speaking", "listening"]):
                asyncio.create_task(self.media_ducking.duck())
            elif "idle" in state_str:
                asyncio.create_task(self.media_ducking.restore())

        self.event_bus.subscribe("orb", "COGNITION_STATE_CHANGED", _on_orb_state)
        self.event_bus.subscribe("state", "EXECUTION_STATE_CHANGED", _on_orb_state)

        # Semantic Environment Pipeline (Phase 4 / 6)WorkspaceSemanticAnalyzer()
        self.semantic_provider = WorkspaceSemanticAnalyzer()
        
        self.workspace_engine = WorkspaceAwarenessEngine(self.window_backend, self.semantic_provider, event_bus=self.event_bus)
        self.attention_engine = AttentionGraphEngine(self.window_backend, event_bus=self.event_bus)
        self.session_manager = SessionManager(self.workspace_engine)
        self.intent_detector = AmbientIntentDetector(
            self.workspace_engine, 
            self.attention_engine, 
            self.session_manager, 
            self.event_bus
        )
        
        # Semantic Environment Graph — the persistent, decaying world-model
        self.environment_graph = SemanticEnvironmentGraph()
        
        # Wire environment events from the EventBus into the Graph
        def _feed_graph(payload):
            from arova.core.environment.events import EnvironmentalEvent
            payload_dict = payload.__dict__ if hasattr(payload, '__dict__') else payload
            if not isinstance(payload_dict, dict):
                payload_dict = {"raw": payload_dict}
            # Unbox DictPayload if needed
            if "data" in payload_dict and isinstance(payload_dict["data"], dict):
                payload_dict = payload_dict["data"]
            # Build an EnvironmentalEvent for generic bus payloads
            ev = EnvironmentalEvent(
                source=payload_dict.get("source", "event_bus"),
                semantic_type=payload_dict.get("semantic_type", "UNKNOWN"),
                confidence=payload_dict.get("confidence", 1.0),
                payload=payload_dict
            )
            self.environment_graph.apply(ev)
        
        self.event_bus.subscribe("environment", "ATTENTION_STATE_CHANGED", _feed_graph)
        self.event_bus.subscribe("environment", "AMBIENT_INTENT_DETECTED", _feed_graph)
        
        # Start OS event listeners and decay loop in background
        import asyncio
        self._bg_tasks = getattr(self, '_bg_tasks', set())
        try:
            loop = asyncio.get_running_loop()
            t1 = loop.create_task(self.window_backend.subscribe_events())
            t2 = loop.create_task(self.environment_graph.start_decay_loop())
            self._bg_tasks.add(t1)
            self._bg_tasks.add(t2)
            t1.add_done_callback(self._bg_tasks.discard)
            t2.add_done_callback(self._bg_tasks.discard)
        except RuntimeError:
            logging.debug("No running asyncio event loop during window/environment graph loop startup; deferred.")
        
        # === TIER 0.3: Cognition Layer (Phase 7 / 12A + Synthesis) — GATED ===
        from arova.core.models.profiles import CognitiveProfile
        from arova.core.cognition.priority import CognitivePriorityEngine, CognitiveSignal
        from arova.core.cognition.modulation import PresenceModulator
        from arova.core.environment.trajectory import AttentionNarrativeGenerator
        
        self.priority_engine = CognitivePriorityEngine()
        if getattr(self, "enable_presence", False):
            self.presence_modulator = PresenceModulator()
            self.narrative_generator = AttentionNarrativeGenerator()
        else:
            self.presence_modulator = None
            self.narrative_generator = None
            logging.info("BETA_MINIMAL: PresenceModulator/NarrativeGenerator disabled")
        
        self.intent_graph = IntentGraph(event_bus=self.event_bus)
        # Seed intents from hot state if present
        for i_dict in self.runtime_snapshot.hot_state.active_intents:
            from arova.core.intention.graph import IntentNode
            self.intent_graph._nodes[i_dict["intent_id"]] = IntentNode.from_dict(i_dict)
        self.continuity_engine = PlanningContinuityEngine(
            intent_graph=self.intent_graph,
            thread_manager=self.session.thread_manager, # Using Session's thread manager
            event_bus=self.event_bus
        )
        
        # Wire Attention Events to Narrative Generator, Modulator, and Continuity — GATED
        if getattr(self, "enable_presence", False) and self.narrative_generator and self.presence_modulator:
            def _feed_narrative(payload):
                if hasattr(payload, 'payload'): # EnvironmentalEvent
                    traj = self.narrative_generator.update(payload.payload)
                    
                    # Update Modulator actively
                    snap = self.environment_graph.snapshot()
                    derived = snap.get("_derived", {})
                    profile = self.presence_modulator.modulate(traj, derived)
                    
                    # Emit to frontend
                    self.event_bus.emit("cognition", "PRESENCE_PROFILE_UPDATED", {
                        "verbosity": profile.verbosity,
                        "cadence": profile.cadence,
                        "emotional_temperature": profile.emotional_temperature,
                        "interruption_sensitivity": profile.interruption_sensitivity,
                        "ambient_density": profile.ambient_density
                    })
                    
                    # Opportunistically evaluate continuity
                    self.continuity_engine.evaluate_resonance(traj, snap)
                    
            self.event_bus.subscribe("environment", "ATTENTION_STATE_CHANGED", _feed_narrative)
        
        # Add IntentGraph decay tick to the background loop
        async def _decay_loops():
            import asyncio
            while True:
                self.intent_graph.tick_decay()
                self._persist_runtime()
                await asyncio.sleep(60.0) # Check intents and save state every minute
                
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_decay_loops())
        except RuntimeError:
            logging.debug("No running asyncio event loop during decay loops initialization; deferred.")
            
        # Wire Memory and Intent events into Priority Engine
        def _feed_priority(payload, visibility="ambient"):
            data = payload.payload if hasattr(payload, 'payload') else payload
            if isinstance(data, dict):
                conf = data.get("confidence", 0.5)
                sig = CognitiveSignal(
                    source=data.get("source", "system"),
                    semantic_type=data.get("semantic_type", "UNKNOWN"),
                    priority=conf,
                    emotional_weight=0.5,
                    visibility=visibility,
                    confidence=conf,
                    decay_rate=0.1,
                    interruptible=True,
                    payload=data
                )
                self.priority_engine.ingest_signal(sig)
                
        self.event_bus.subscribe("memory", "MEMORY_RECALLED", lambda p: _feed_priority(p, "foreground"))
        self.event_bus.subscribe("environment", "AMBIENT_INTENT_DETECTED", lambda p: _feed_priority(p, "ambient"))
        
        # Phase 3 Intention Events
        # Phase 5.75: Runtime Projection Layer
        from arova.core.projection.projector import RuntimeProjector
        self.runtime_projector = RuntimeProjector(
            session_manager=self.session,
            thread_manager=self.session.thread_manager,
            environment_graph=self.environment_graph
        )
        
        # We also want to wire a projection event emission on major state changes
        def _emit_projection(payload):
            # Don't emit if it's just a background tick, only when UI needs it
            proj = self.runtime_projector.project()
            self.event_bus.emit("projection", "PROJECTION_UPDATED", proj.to_dict())
            
        self.event_bus.subscribe("cognition", "THREAD_SYNC", _emit_projection)
        self.event_bus.subscribe("voice", "TEXT_RESPONSE_GENERATED", _emit_projection)
        self.event_bus.subscribe("voice", "TRANSCRIPT_FINAL", _emit_projection)
        self.event_bus.subscribe("automation", "GRAPH_EXECUTION_REQUESTED", _emit_projection)
        self.event_bus.subscribe("automation", "NODE_STATE_CHANGED", _emit_projection)
        self.event_bus.subscribe("automation", "GRAPH_EXECUTION_COMPLETED", _emit_projection)
        self.event_bus.subscribe("intention", "INTENT_PRESSURE_HIGH", lambda p: _feed_priority(p, "ambient"))
        self.event_bus.subscribe("intention", "CONTINUITY_RESONANCE_SPIKE", lambda p: _feed_priority(p, "ambient"))
        
        self.model_runtime = ModelOrchestrator(config=self.config, active_profile=CognitiveProfile.BALANCED, event_bus=self.event_bus)
        self.model_orchestrator = self.model_runtime
        if hasattr(self, 'workspace_manager') and self.workspace_manager:
            self.workspace_manager.orchestrator = self.model_runtime
        self.memory_runtime.set_orchestrator(self.model_runtime)
        
        from arova.core.timeline.momentum import CapsuleGenerator, MomentumTracker
        self.capsule_generator = CapsuleGenerator(timeline_store=self.timeline, orchestrator=self.model_runtime)
        self.momentum_tracker = MomentumTracker(event_bus=self.event_bus, capsule_generator=self.capsule_generator)
        
        self.cognitive_trace = CognitiveTraceEngine(event_bus=self.event_bus)
        self.memory_retrieval = MemoryRetrievalEngine(memory_runtime=self.memory_runtime)
        
        self.ambient_observer.narrative_generator = self.narrative_generator

        self.context_synthesizer = ContextSynthesizer(
            provider_manager=self.provider_manager,
            memory_retrieval=self.memory_retrieval,
            ambient_observer=self.ambient_observer,
            policy_runtime=self.policy_runtime,
            environment_graph=self.environment_graph,
            presence_modulator=self.presence_modulator,
            narrative_generator=self.narrative_generator,
            workspace_manager=self.workspace_manager,
            timeline_store=self.timeline,
            capsule_generator=self.capsule_generator,
            search_index=self.search_index
        )
        self.cognitive_router = CognitiveRouter(model_runtime=self.model_runtime, event_bus=self.event_bus)
        self.cognitive_planner = CognitivePlanner(model_runtime=self.model_runtime)
        
        from arova.core.cognition.action_planner import ActionPlanner
        self.action_planner = ActionPlanner(model_runtime=self.model_runtime)
    
        if getattr(self, "enable_voice", False):
            from arova.core.voice.voice_runtime import VoiceRuntime
            self.voice_runtime = VoiceRuntime(event_bus=self.event_bus)
        else:
            self.voice_runtime = None
            logging.info("BETA_MINIMAL: VoiceRuntime disabled")
        from arova.core.voice.intent_runtime import IntentRuntime
        self.intent_runtime = IntentRuntime(
            event_bus=self.event_bus, 
            session=self.session,
            router=self.cognitive_router,
            context_synthesizer=self.context_synthesizer,
            planner=self.cognitive_planner,
            action_planner=self.action_planner
        )
        self.intent_runtime._workspace_manager = self.workspace_manager
    
        if getattr(self, "enable_voice", False) and getattr(self, "cancellation", None) and getattr(self, "audio_session", None):
            from arova.core.voice.tts_runtime import TTSRuntime
            self.tts_runtime = TTSRuntime(event_bus=self.event_bus, config=self.config, 
                                          cancellation=self.cancellation, audio_manager=self.audio_session)
        else:
            self.tts_runtime = None
            logging.info("BETA_MINIMAL: TTSRuntime disabled")
            
        from arova.core.automation.dispatcher import ActionDispatcher
        from arova.core.automation.execution_runtime import ExecutionRuntime
        self.action_dispatcher = ActionDispatcher(orchestrator=self.model_runtime, workspace_manager=self.workspace_manager)
        self.execution_runtime = ExecutionRuntime(event_bus=self.event_bus, dispatcher=self.action_dispatcher)
        if getattr(self, 'runtime_projector', None):
            self.runtime_projector.execution_runtime = self.execution_runtime
    def _persist_runtime(self):
        """Serializes hot runtime state into the canonical RuntimeSnapshot and saves it."""
        try:
            # Update Hot State
            self.runtime_snapshot.hot_state.recent_turns = self.session._legacy_messages[-20:] # Keep last 20 turns
            self.runtime_snapshot.hot_state.active_threads = [
                t.to_dict() if hasattr(t, 'to_dict') else t for t in self.session.thread_manager.get_all_threads()
            ]
            self.runtime_snapshot.hot_state.active_intents = [
                i.to_dict() if hasattr(i, 'to_dict') else i for i in self.intent_graph.get_all_intents()
            ]
            if hasattr(self, 'workspace_manager'):
                self.runtime_snapshot.hot_state.workspaces = {
                    wid: w.to_dict() if hasattr(w, 'to_dict') else w
                    for wid, w in self.workspace_manager._workspaces.items()
                }
                self.runtime_snapshot.hot_state.active_workspace_id = self.workspace_manager._active_workspace_id
            
            # Update Crash Recovery (If there is an active turn, mark it)
            if self.session._active_turn and not self.session._active_turn.timestamp_end:
                from arova.core.persistence.schema import CrashRecoveryCheckpoint
                self.runtime_snapshot.recovery_checkpoint = CrashRecoveryCheckpoint(
                    interrupted_stream=self.session._active_turn.user_transcript,
                    recovered=False
                )
                
            self.runtime_store.save(self.runtime_snapshot)
        except Exception as e:
            import logging
            import traceback
            logging.error(f"Failed to persist runtime state: {e}\n{traceback.format_exc()}")
        

    def shutdown(self):
        """Gracefully shut down all thread pools and event buses."""
        execution_logger.log("RUNTIME_SHUTDOWN", message="Shutting down runtime container")
        try:
            self._persist_runtime()
        except Exception as e:
            logging.error(f"Failed to persist runtime during shutdown: {e}")
        if getattr(self, 'watchdog', None):
            try:
                self.watchdog.stop()
            except: pass
        if getattr(self, 'ambient_observer', None):
            try:
                self.ambient_observer.stop()
            except: pass
        if getattr(self, 'turn_coordinator', None):
            try:
                self.turn_coordinator.stop()
            except: pass
        self.event_bus.shutdown(wait=True)
        self.thread_manager.shutdown(wait=True)
        
    def get_health_snapshot(self) -> dict:
        return {
            "authoritative_turn_id": self.session.get_authoritative_turn_id(),
            "voice_runtime": self.voice_runtime.get_health_snapshot() if getattr(self, 'voice_runtime', None) else {"status": "disabled_beta_minimal"},
            "beta_mode": getattr(self, 'beta_mode', 'unknown'),
            "voice_enabled": getattr(self, 'enable_voice', False)
        }
