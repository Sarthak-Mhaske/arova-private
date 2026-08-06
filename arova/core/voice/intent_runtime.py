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
        Receives final transcripts and parses them — now with @-mention grounding.
        """
        transcript = payload.transcript if hasattr(payload, 'transcript') else payload.get("transcript", "") if isinstance(payload, dict) else str(payload)
        turn_id = getattr(payload, "turn_id", None)
        if turn_id is None and isinstance(payload, dict):
            turn_id = payload.get("turn_id")
        elif turn_id is None and hasattr(payload, 'data') and isinstance(payload.data, dict):
            turn_id = payload.data.get("turn_id")
        vocalize = getattr(payload, "vocalize", True)
        if isinstance(payload, dict):
            vocalize = payload.get("vocalize", vocalize)
        elif hasattr(payload, 'data') and isinstance(payload.data, dict):
            vocalize = payload.data.get("vocalize", vocalize)
        # Extract mentions — daemon parses @mentions and sends explicit list
        mentions = []
        if isinstance(payload, dict):
            mentions = payload.get("mentions", []) or []
        elif hasattr(payload, 'data') and isinstance(payload.data, dict):
            mentions = payload.data.get("mentions", []) or []
            # DictPayload also may have transcript as data field, check mentions there
            if not mentions and isinstance(payload.data.get("mentions"), list):
                mentions = payload.data.get("mentions") or []
        if hasattr(payload, 'mentions') and not mentions:
            # EventBus wraps dict payloads into DictPayload, so check attribute
            try:
                attr = getattr(payload, 'mentions')
                if isinstance(attr, list) and attr:
                    mentions = attr
            except:
                pass
        # Normalize mentions
        if mentions is None:
            mentions = []
        if isinstance(mentions, str):
            mentions = [mentions]
        mentions = [str(m).strip().lstrip('@').strip() for m in mentions if str(m).strip()]
        
        # We execute this inside an asyncio task on the main loop
        if self._loop:
            # Cancel any existing task just in case
            if self._active_stream_task and not self._active_stream_task.done():
                self._active_stream_task.cancel()
                
            fut = asyncio.run_coroutine_threadsafe(self._process_transcript_cognition(transcript, turn_id, vocalize, mentions), self._loop)
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
        
    async def _process_transcript_cognition(self, transcript: str, turn_id: str, vocalize: bool = True, mentions: list = None):
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
            
        # 3. Standard / Chat (Streaming response) — TIER 1 MOAT: Grounded synthesis
        logging.info(f"IntentRuntime invoked for turn_id={turn_id} (mentions={mentions})")
        self._event_bus.emit("cognition", "COGNITION_STATE_CHANGED", {"state": "GENERATING_RESPONSE", "details": ""})
        
        # === TIER 1.1+1.3: Grounded synthesis — verbatim deterministic state ===
        base_prompt = "You are Arova, a working-memory OS. You answer from VERBATIM ground truth, not hallucinations. Be concise, cite exact files/terminals, and hedge if confidence is low."
        try:
            cognitive_context = await self._context_synthesizer.synthesize(transcript, mentions=mentions or [])
            grounded_block = cognitive_context.to_system_prompt_block()
        except Exception as e:
            logging.warning(f"Grounded synthesis failed, falling back to legacy: {e}")
            grounded_block = ""
            cognitive_context = None

        # Legacy fallback parts (for extra memory context if synthesizer missed)
        memory_context = ""
        try:
            if hasattr(self._session, "_memory_runtime") and self._session._memory_runtime:
                memory_context = await self._session._memory_runtime.recall_context()
        except:
            pass
            
        # Build final sys_prompt: base + grounded (primary) + memory
        prompt_parts = [base_prompt]
        if grounded_block:
            prompt_parts.append(grounded_block)
        else:
            # Legacy fallback
            workspace_manager = getattr(self, '_workspace_manager', None) or getattr(self._session, 'workspace_manager', None) or getattr(self._context_synthesizer, 'workspace_manager', None)
            workspace_summary = ""
            if workspace_manager:
                active_ws = workspace_manager.get_active_workspace()
                if active_ws and hasattr(active_ws, 'get_workspace_summary_prompt'):
                    workspace_summary = active_ws.get_workspace_summary_prompt()
            if workspace_summary:
                prompt_parts.append(workspace_summary)
            elif getattr(self._session, '_system_prompt', None):
                prompt_parts.append(f"=== Active Context ===\n{self._session._system_prompt}")
            
        if memory_context and "MEMORY LAYER" not in grounded_block:
            prompt_parts.append(f"=== Long-Term User Profile (Layer 1) ===\n{memory_context}")
            
        sys_prompt = "\n\n".join(prompt_parts)        
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
        stream_success = False
        try:
            async for token in self._router.models.invoke_stream(messages, sys_prompt, depth=ReasoningDepth.STANDARD):
                full_text += token
                await buffer.append(token)
                stream_success = True
        except Exception as e:
            logging.warning(f"IntentRuntime LLM stream failed, will use grounded mock fallback: {e}")
            stream_success = False

        # === TIER 1 MOAT FALLBACK: If no tokens or provider error, synthesize grounded mock ===
        is_error_response = any(phrase in full_text.lower() for phrase in ["unable to connect", "no inference provider", "max retries exceeded", "connection refused"])
        if not stream_success or not full_text.strip() or is_error_response:
            # Check if grounded context has verbatim resources to cite
            grounded = getattr(cognitive_context, 'grounded_resources', None) if 'cognitive_context' in locals() else None
            active_ws = None
            try:
                wm = getattr(self, '_workspace_manager', None) or getattr(self._session, 'workspace_manager', None) or getattr(self._context_synthesizer, 'workspace_manager', None)
                if wm:
                    active_ws = wm.get_active_workspace()
            except:
                pass
            # Build grounded mock answer — this IS the moat demo without LLM
            if active_ws and transcript.strip().lower() in ["where was i?", "where was i", "what was i doing", "resume", "what's next", "whats next", "continue"] or "where" in transcript.lower() or "what was" in transcript.lower():
                # Grounded resume answer
                title = getattr(active_ws, 'title', 'your workspace')
                goal = getattr(active_ws.understanding.momentum, 'goal', 'continuing work') if hasattr(active_ws, 'understanding') else 'continuing work'
                blocker = getattr(active_ws.understanding.momentum, 'current_blocker', None) if hasattr(active_ws, 'understanding') else None
                nxt = getattr(active_ws.understanding.momentum, 'next_action', None) if hasattr(active_ws, 'understanding') else None
                conf = getattr(active_ws.understanding.confidence, 'score', 0) if hasattr(active_ws, 'understanding') else 0
                hedge = "I think " if 0 < conf < 70 else ""
                # Cite verbatim resources
                res_list = list(active_ws.reality.resources.keys())[:3] if hasattr(active_ws, 'reality') and active_ws.reality.resources else []
                res_cite = ", ".join([r.split('/')[-1] for r in res_list]) if res_list else "your recent files"
                mock_answer = f"{hedge}You were working on **{title}** — {goal}. "
                if res_list:
                    mock_answer += f"Last observed: `{res_list[0]}`" 
                    if len(res_list) > 1:
                        mock_answer += f" and `{res_list[1]}`"
                    mock_answer += ". "
                if blocker:
                    mock_answer += f"Blocker: {blocker}. "
                if nxt:
                    mock_answer += f"Next: {nxt}."
                else:
                    mock_answer += "Ready to continue?"
                # Add grounded humility
                if 0 < conf < 70:
                    mock_answer += f" ({conf}% confidence — please verify)"
                # Emit mock as stream
                for chunk in [mock_answer[i:i+60] for i in range(0, len(mock_answer), 60)]:
                    await buffer.append(chunk)
                full_text = mock_answer
            elif grounded and "@" in transcript and cognitive_context and getattr(cognitive_context, 'mentioned_resources', None):
                # @-mention mock: cite file excerpt
                mock_answer = f"Got it — you @-mentioned a file. Here's the verbatim context I'm grounding on:\n\n{cognitive_context.mentioned_resources[:800]}\n\nBased on that, the issue is around the code above. Want me to trace the flow?"
                for chunk in [mock_answer[i:i+60] for i in range(0, len(mock_answer), 60)]:
                    await buffer.append(chunk)
                full_text = mock_answer
            elif cognitive_context and getattr(cognitive_context, 'search_results', None):
                # Search unification mock: cite verbatim unified index hits
                hits = cognitive_context.search_results[:600]
                mock_answer = f"Found via unified search (verbatim, no hallucination):\n\n{hits}\n\nAbove are exact hits from your local index — files, decisions, docs. Want me to open one?"
                for chunk in [mock_answer[i:i+60] for i in range(0, len(mock_answer), 60)]:
                    await buffer.append(chunk)
                full_text = mock_answer
            else:
                # Generic grounded fallback
                if not full_text.strip():
                    fallback = "I'm in minimal demo mode (no LLM key). But I can still answer from your VERBATIM ground truth — try `where was I?` or `@runtime.py what's stuck?`"
                    await buffer.append(fallback)
                    full_text = fallback
            
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
