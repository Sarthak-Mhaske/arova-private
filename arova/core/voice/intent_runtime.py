import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from arova.core.events import RuntimeEventBus
import asyncio
from arova.core.models.schema import ReasoningDepth, ReasoningBudget
from arova.core.cognition.router import CognitiveRouter
from arova.core.cognition.context import ContextSynthesizer
from arova.core.cognition.planner import CognitivePlanner

@dataclass(frozen=True)
class Intent:
    """Structured Semantic Intent representing user's parsed goal."""
    type: str
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    references: List[str] = field(default_factory=list)

class IntentRuntime:
    """
    Parses final transcripts using Phase 7/7.5 Cognitive Pipeline.
    """
    
    def __init__(self, event_bus: RuntimeEventBus, session: Any,
                 router: CognitiveRouter, 
                 context_synthesizer: ContextSynthesizer, 
                 planner: CognitivePlanner):
        self._event_bus = event_bus
        self._session = session
        self._router = router
        self._context_synthesizer = context_synthesizer
        self._planner = planner
        
        # State for active stream preemption
        self._active_stream_task: Optional[asyncio.Task] = None
        
        try:
            self._loop = asyncio.get_running_loop()
            logging.info(f"IntentRuntime: Captured asyncio loop: {self._loop}")
        except RuntimeError:
            self._loop = None
            logging.error("IntentRuntime: NO asyncio loop available at init!")
            
        # Subscribe to final transcripts and interrupts
        self._event_bus.subscribe("voice", "TRANSCRIPT_FINAL", self._on_transcript)
        self._event_bus.subscribe("runtime", "INTERRUPT_REQUESTED", self._on_interrupt)
        
    def _on_interrupt(self, payload):
        """Preempt the active cognition stream."""
        if self._active_stream_task and not self._active_stream_task.done():
            logging.info("IntentRuntime: Cancelling active LLM stream due to interrupt.")
            self._active_stream_task.cancel()
            self._event_bus.emit("cognition", "STREAM_INTERRUPTED", {})
            self._active_stream_task = None

    def _on_transcript(self, payload):
        """
        Receives final transcripts and parses them.
        """
        transcript = payload.transcript
        turn_id = getattr(payload, "turn_id", None)
        vocalize = getattr(payload, "vocalize", True)
        
        # We execute this inside an asyncio task on the main loop
        if self._loop:
            # Cancel any existing task just in case
            if self._active_stream_task and not self._active_stream_task.done():
                self._active_stream_task.cancel()
                
            fut = asyncio.run_coroutine_threadsafe(self._process_transcript_cognition(transcript, turn_id, vocalize), self._loop)
            self._active_stream_task = fut
            
            def on_done(f):
                try:
                    f.result()
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    import logging
                    logging.error(f"IntentRuntime cognition failed: {e}", exc_info=True)
            fut.add_done_callback(on_done)
        else:
            import logging
            logging.error("IntentRuntime: No event loop captured at initialization!")
        
    async def _process_transcript_cognition(self, transcript: str, turn_id: str, vocalize: bool = True):
        logging.info(f"IntentRuntime: _process_transcript_cognition entered. transcript='{transcript}', turn_id={turn_id}")
        
        # Phase 2: Trigger memory ghost recall asynchronously before responding
        if hasattr(self._session, "_memory_runtime") and self._session._memory_runtime:
            await self._session._memory_runtime.recall_ghosts_for_transcript(transcript)
        
        # 1. Routing
        # Use existing turn if provided (by main.py or voice runtime), else start new
        if not turn_id or not self._session.is_authoritative(turn_id):
            turn = self._session.start_new_turn(transcript)
            turn_id = turn.turn_id
        messages = self._session.build_api_messages(max_turns=10)
        logging.info("IntentRuntime: Calling router.route()...")
        intent_class = await self._router.route(messages)
        logging.info(f"IntentRuntime: Router returned category={intent_class.category}, depth={intent_class.depth}")
        
        if intent_class.category == "fast_action":
            # Direct bypass
            self._event_bus.emit("automation", "GRAPH_EXECUTION_REQUESTED", {
                "graph": intent_class.fast_path_graph,
                "turn_id": turn_id
            })
            return
            
        if intent_class.depth == ReasoningDepth.DEEP:
            # Full planning
            context = await self._context_synthesizer.synthesize(transcript)
            plan = await self._planner.generate_graph(messages, context, budget=ReasoningBudget())
            if plan:
                self._event_bus.emit("automation", "GRAPH_EXECUTION_REQUESTED", {
                    "graph": plan,
                    "turn_id": turn_id
                })
            return
            
        # 3. Standard / Chat (Streaming response to TTS)
        logging.info(f"IntentRuntime invoked for turn_id={turn_id}")
        self._event_bus.emit("cognition", "COGNITION_STATE_CHANGED", {"state": "GENERATING_RESPONSE", "details": ""})
        
        base_prompt = "You are Arova. Reply conversationally and briefly. Do not use tools."
        memory_context = ""
        if hasattr(self._session, "_memory_runtime") and self._session._memory_runtime:
            memory_context = await self._session._memory_runtime.recall_context()
            
        sys_prompt = f"{base_prompt}\n\n{memory_context}" if memory_context else base_prompt        
        # Stream chunks directly to TTS Runtime (Phase 7.5 streaming TTS)
        logging.info(f"IntentRuntime: Emitting stream start for {turn_id}")
        self._event_bus.emit("voice", "TEXT_STREAM_STARTED", {
            "turn_id": turn_id
        })
        
        async def _on_chunk_batch(text_chunk: str, seq: int):
            logging.info(f"IntentRuntime: LLM batch seq {seq}: '{text_chunk}'")
            self._event_bus.emit("voice", "TEXT_CHUNK_GENERATED", {
                "text": text_chunk,
                "turn_id": turn_id,
                "vocalize": vocalize,
                "seq": seq
            })
            
        from arova.core.cognition.buffer import AsyncDeltaBuffer
        buffer = AsyncDeltaBuffer(_on_chunk_batch, flush_interval_s=0.05)
        
        full_text = ""
        async for token in self._router.models.invoke_stream(messages, sys_prompt, depth=ReasoningDepth.STANDARD):
            full_text += token
            await buffer.append(token)
            
        await buffer.close()
        
        if hasattr(self, "_session") and self._session:
            self._session.add_assistant_message(full_text)
            
        # Signal EOF to TTSRuntime
        logging.info(f"IntentRuntime: LLM stream complete. Emitting stream end for {turn_id}.")
        self._event_bus.emit("voice", "TEXT_RESPONSE_GENERATED", {
            "text": "",
            "turn_id": turn_id,
            "vocalize": vocalize
        })
