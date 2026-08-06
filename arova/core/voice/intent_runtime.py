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
                 planner: CognitivePlanner,
                 action_planner: Any):
        self._event_bus = event_bus
        self._session = session
        self._router = router
        self._context_synthesizer = context_synthesizer
        self._planner = planner
        self._action_planner = action_planner
        
        # Track pending graph executions by turn_id to await their results
        self._pending_executions: Dict[str, asyncio.Future] = {}
        
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
        self._event_bus.subscribe("automation", "GRAPH_EXECUTION_COMPLETED", self._on_graph_completed)

    def _on_graph_completed(self, payload: Any):
        """Called when ExecutionRuntime finishes a graph."""
        if hasattr(payload, 'data') and isinstance(payload.data, dict):
            turn_id = payload.data.get("turn_id")
        else:
            turn_id = getattr(payload, "turn_id", None)
            
        if turn_id and turn_id in self._pending_executions:
            fut = self._pending_executions[turn_id]
            if not fut.done() and self._loop:
                self._loop.call_soon_threadsafe(fut.set_result, payload)

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
        transcript = getattr(payload, "transcript", None) or (payload.get("transcript") if isinstance(payload, dict) else "")
        turn_id = getattr(payload, "turn_id", None) or (payload.get("turn_id") if isinstance(payload, dict) else None)
        source = getattr(payload, "source", "voice") or (payload.get("source") if isinstance(payload, dict) else "voice")
        vocalize = getattr(payload, "vocalize", True) if not isinstance(payload, dict) else payload.get("vocalize", True)
        
        # Voice & Wake Word transcripts MUST always trigger TTS vocalization!
        if source in ("voice", "wake_word", "stt"):
            vocalize = True
        
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
        self._event_bus.emit("state", "EXECUTION_STATE_CHANGED", {"state": "THINKING", "turn_id": turn_id})
        try:
            # Phase 2: Trigger memory ghost recall asynchronously before responding
            if hasattr(self._session, "_memory_runtime") and self._session._memory_runtime:
                await self._session._memory_runtime.recall_ghosts_for_transcript(transcript)
            
            # 1. Start turn if needed
            if not turn_id or not self._session.is_authoritative(turn_id):
                turn = self._session.start_new_turn(transcript)
                turn_id = turn.turn_id

            # 2. Pre-routing keyword workspace restore check (no LLM needed)
            lower = transcript.lower().strip()
            restore_phrases = [
                "restore the apps", "restore apps", "restore my apps", "open the apps", "open apps",
                "open those apps", "restore those apps", "open all these apps", "open these apps",
                "restore workspace", "restore context", "restore environment", "restore files",
                "restore the files", "restore all", "restore project", "open workspace", "resume work",
                "open all apps"
            ]
            is_keyword_restore = lower in restore_phrases
            
            workspace_manager = getattr(self, '_workspace_manager', None) or getattr(self._session, 'workspace_manager', None) or getattr(self._context_synthesizer, 'workspace_manager', None)
            active_ws = workspace_manager.get_active_workspace() if workspace_manager else None

            if is_keyword_restore and workspace_manager and active_ws:
                workspace_manager.restore_environment(active_ws, {"restore_all": True})
                active_ws._restored = True
                    
                resources_list = list(active_ws.reality.resources.keys())[:3]
                resources_str = ", ".join([r.split('/')[-1] for r in resources_list]) if resources_list else "project files"
                next_act = active_ws.understanding.momentum.next_action or "continue current development trajectory"
                
                if self._event_bus:
                    self._event_bus.emit("cognition", "surfacing_push", {
                        "type": "surfacing",
                        "kind": "momentum",
                        "from": "AROVA · CONTEXT RECOVERY",
                        "lede": f"Restored {active_ws.title}",
                        "paragraphs": [
                            f"**Restored Workspace**: {active_ws.title}",
                            f"**Active Resources**: {resources_str}",
                            f"**Next Action**: {next_act}"
                        ],
                        "actions": [
                            {"label": "Resume & Restore All", "eventType": "workspace.continue", "eventPayload": {"workspace_id": active_ws.workspace_id, "options": {"restore_all": True}}, "primary": True},
                            {"label": "Choose What To Restore", "clientAction": "open_options"},
                            {"label": "Dismiss", "clientAction": "dismiss"}
                        ]
                    })

            # 3. Single route call with full conversation history (Bug 6 fix: removed redundant first call)
            messages = self._session.build_api_messages(max_turns=10)
            if is_keyword_restore and active_ws:
                messages.append({
                    "role": "system",
                    "content": f"You just successfully restored the user's workspace '{active_ws.title}'. Briefly acknowledge this and then answer the rest of their query naturally."
                })
            logging.info("IntentRuntime: Calling router.route()...")
            intent_class = await self._router.route(messages)
            
            # If router also detected restore intent, handle it
            is_llm_restore = intent_class.category == "restore_workspace" or \
                (intent_class.fast_path_graph and "Restore Environment" in getattr(intent_class.fast_path_graph, 'name', ''))
            if is_llm_restore and not is_keyword_restore and workspace_manager and active_ws:
                workspace_manager.restore_environment(active_ws, {"restore_all": True})
                active_ws._restored = True
            
            logging.info(f"IntentRuntime: Router returned category={intent_class.category}, depth={intent_class.depth}")
            
            if intent_class.category in ("fast_action", "action"):
                graph = None
                feedback_message = "Executing action..."
                
                if intent_class.category == "fast_action" and intent_class.fast_path_graph:
                    graph = intent_class.fast_path_graph
                    feedback_message = f"I'm executing {graph.name}."
                else:
                    self._event_bus.emit("state", "EXECUTION_STATE_CHANGED", {"state": "THINKING", "turn_id": turn_id})
                    self._event_bus.emit("cognition", "COGNITION_STATE_CHANGED", {"state": "PLANNING_ACTION", "details": "Synthesizing context & selecting capabilities..."})
                    # Use ActionPlanner to generate graph
                    context = await self._context_synthesizer.synthesize(transcript)
                    action_plan = await self._action_planner.generate_action_plan(messages, context, budget=ReasoningBudget())
                    if action_plan:
                        graph, feedback_message = action_plan
                
                if graph:
                    # Execute graph and await results
                    self._event_bus.emit("state", "EXECUTION_STATE_CHANGED", {"state": "EXECUTING", "turn_id": turn_id})
                    self._event_bus.emit("cognition", "COGNITION_STATE_CHANGED", {"state": "EXECUTING_ACTION", "details": f"Executing: {graph.name}"})
                    
                    # 1. Start the text stream early for dynamic node state updates
                    if self._event_bus:
                        self._event_bus.emit("voice", "TEXT_STREAM_STARTED", {"turn_id": turn_id})
                    
                    fut = self._loop.create_future()
                    self._pending_executions[turn_id] = fut
                    
                    self._event_bus.emit("automation", "GRAPH_EXECUTION_REQUESTED", {
                        "graph": graph,
                        "turn_id": turn_id,
                        "feedback_message": feedback_message
                    })
                    
                    try:
                        # Wait up to 120 seconds for execution to complete
                        result_payload = await asyncio.wait_for(fut, timeout=120.0)
                        
                        if hasattr(result_payload, 'data') and isinstance(result_payload.data, dict):
                            success = result_payload.data.get("success", False)
                            results = result_payload.data.get("results", [])
                        else:
                            success = getattr(result_payload, "success", False)
                            results = getattr(result_payload, "results", [])
                            
                        # Check if any action node produced rich informational analysis output (ONLY for analyze_screen or read_file)
                        info_output = None
                        for res in results:
                            if isinstance(res, dict) and res.get("status") == "success":
                                cap = res.get("capability", "")
                                out = res.get("output", "")
                                if cap in ("analyze_screen", "read_file") and out and len(out) > 40:
                                    info_output = out
                                    break
                                    
                        final_msg = ""
                        if info_output:
                            # Preserve the full, detailed rich markdown analysis from vision/file tools for the UI
                            final_msg = info_output.strip()
                        else:
                            # Generate refined LLM response that directly answers the user's prompt & summarizes actions
                            user_home = os.path.expanduser("~")
                            prompt = (
                                f"The user asked: '{transcript}'.\n"
                                f"I executed these background actions for them: {results}.\n"
                                "Instructions:\n"
                                "1. If the user asked a question or wanted advice, a roadmap, or recommendations, ANSWER THEM directly, warmly, and completely.\n"
                                "2. Briefly mention what actions were taken for them (e.g. 'I've also opened the link in your browser').\n"
                                f"3. EXPLICIT FOLDER / PATH MENTION: If a folder, directory, file, or project was created or opened, EXPLICITLY state its exact real path e.g. '{user_home}/PythonLearning' or '~/PythonLearning'. NEVER use fake paths like '/home/user'.\n"
                                "4. FORMATTING RULE: Do NOT wrap URLs or file paths in broken bold asterisks `**` across line breaks. Write URLs as plain `https://...` or standard markdown links [text](url). Write file paths in plain text or code ticks e.g. `~/PythonLearning`.\n"
                                "5. Respond in natural conversational text."
                            )
                            try:
                                final_msg = await self._router.models.generate(
                                    messages=messages + [{"role": "user", "content": prompt}],
                                    system_prompt="You are Arova, a helpful ambient AI assistant. Give a warm, helpful, complete answer to the user.",
                                    depth=ReasoningDepth.STANDARD,
                                    budget=ReasoningBudget(max_tokens=600)
                                )
                            except Exception as e:
                                logging.error(f"Failed to generate refined response: {e}")
                                if success:
                                    if graph and hasattr(graph, 'name') and graph.name:
                                        final_msg = f"Done! I've completed: {graph.name}."
                                    elif feedback_message and feedback_message != "Executing action...":
                                        final_msg = f"Done! {feedback_message}"
                                    else:
                                        final_msg = "Done! I've executed the requested actions."
                                else:
                                    final_msg = "I attempted the action, but it didn't complete successfully. Let me know if you'd like me to try again."
                        final_msg = final_msg.strip()
                            
                    except asyncio.TimeoutError:
                        final_msg = "The action is taking longer than expected, but it is running in the background."
                    finally:
                        self._pending_executions.pop(turn_id, None)
                    
                    self._event_bus.emit("state", "EXECUTION_STATE_CHANGED", {"state": "IDLE", "turn_id": turn_id})
                    
                    if self._event_bus:
                        # For voice TTS, extract a clean 1-2 sentence spoken summary if output is long
                        vocal_text = final_msg
                        if len(final_msg) > 200 and "\n" in final_msg:
                            first_para = final_msg.split("\n\n")[0].replace("*", "").replace("#", "").strip()
                            vocal_text = first_para if len(first_para) < 250 else final_msg[:200] + "..."

                        self._event_bus.emit("voice", "TEXT_CHUNK_GENERATED", {
                            "text": final_msg,
                            "turn_id": turn_id,
                            "vocalize": vocalize,
                            "spoken_text": vocal_text,
                            "seq": 2
                        })
                        self._event_bus.emit("voice", "TEXT_RESPONSE_GENERATED", {"turn_id": turn_id, "text": final_msg})
                    if self._session:
                        self._session.add_assistant_message(final_msg)
                    return
                
                # If ActionPlanner failed, fall through to Chat
                
            if intent_class.depth == ReasoningDepth.DEEP and intent_class.category != "action":
                # Full planning (non-action, e.g. code generation)
                context = await self._context_synthesizer.synthesize(transcript)
                plan = await self._planner.generate_graph(messages, context, budget=ReasoningBudget())
                if plan:
                    self._event_bus.emit("automation", "GRAPH_EXECUTION_REQUESTED", {
                        "graph": plan,
                        "turn_id": turn_id
                    })
                    
                    short_msg = "I'm on it."
                    if self._event_bus:
                        self._event_bus.emit("voice", "TEXT_STREAM_STARTED", {"turn_id": turn_id})
                        self._event_bus.emit("voice", "TEXT_CHUNK_GENERATED", {
                            "text": short_msg,
                            "turn_id": turn_id,
                            "vocalize": vocalize,
                            "seq": 1
                        })
                        self._event_bus.emit("voice", "TEXT_RESPONSE_GENERATED", {"turn_id": turn_id, "text": short_msg})
                    if self._session:
                        self._session.add_assistant_message(short_msg)
                    return
                
            # 3. Standard / Chat (Streaming response to TTS)
            logging.info(f"IntentRuntime invoked for turn_id={turn_id}")
            self._event_bus.emit("cognition", "COGNITION_STATE_CHANGED", {"state": "GENERATING_RESPONSE", "details": ""})
            
            identity_block = (
                "========================\n"
                "1. WHO YOU ARE\n"
                "========================\n"
                "You are Arova — an ambient operating system layer that runs natively on the user's desktop.\n"
                "You are NOT a chatbot. You are a persistent, context-aware intelligence woven into their daily workflow.\n"
                "You are NOT the user. You never claim ownership of the user's projects, code, or work.\n"
                "\n"
                "YOUR CORE CAPABILITIES (explain these thoroughly when asked):\n"
                "• AMBIENT INTELLIGENCE: You observe the user's desktop environment — open apps, active windows, \n"
                "  media playback, system state — and build a continuous understanding of their workflow trajectory.\n"
                "• SEMANTIC MEMORY: You learn facts, preferences, and patterns about the user over time. This memory \n"
                "  is persistent across sessions — you remember their projects, tools, habits, and interests.\n"
                "• WORKSPACE RESTORATION: When the user returns after being away, you can restore their full working \n"
                "  context — the apps they had open, the files they were editing, the tabs they were browsing.\n"
                "• SYSTEM CONTROL: You can open/close apps, control media playback, adjust volume, search the web, \n"
                "  take screenshots, launch files/folders, focus specific windows, and run shell commands.\n"
                "• SCREEN ANALYSIS: You can take a screenshot and analyze what's currently on screen to answer \n"
                "  questions about visible content (but you need to take a screenshot first — you don't have a \n"
                "  persistent live video feed of their screen).\n"
                "• COGNITIVE THREADING: You track multiple conversation threads and can resume context from earlier \n"
                "  in the session without the user repeating themselves.\n"
                "• PROACTIVE AWARENESS: You detect work patterns and can surface relevant context, suggest next \n"
                "  actions, and help the user resume flow after interruptions.\n"
                "• PRIVACY-FIRST: Everything runs locally on their machine. Their data never leaves their device \n"
                "  except for LLM inference calls which use only the immediate conversation context.\n"
                "\n"
                "WHEN EXPLAINING YOURSELF TO NEW USERS:\n"
                "Be thorough and specific. Don't just list features — explain how each one helps in daily life. \n"
                "Give concrete examples: 'When you come back to your desk in the morning, I can restore exactly \n"
                "where you left off — the VS Code files you had open, the browser tabs, even the Spotify playlist.' \n"
                "Make the user understand WHY Arova is valuable, not just WHAT it can do.\n"
                "\n"
                "CHAT PATH BEHAVIOR:\n"
                "You are currently in the conversational chat path. If the user asks you to perform an action \n"
                "(open an app, play music, etc.), you CAN do it — but you need them to phrase it as a clear command. \n"
                "Guide them: 'Absolutely, just say something like: open brave' or 'Sure, try: play music'.\n"
                "Never say 'I cannot' or 'I don't have the ability' — you DO have these abilities."
            )

            # ── ADAPTIVE VERBOSITY ──
            # Determine response length based on: voice vs chat, and explicit detail signals
            lower_transcript = transcript.lower()
            explicit_detail = any(w in lower_transcript for w in [
                "in depth", "in detail", "detailed", "thorough", "comprehensive", 
                "explain in detail", "elaborate", "tell me everything", "full explanation",
                "deep dive", "tell me all"
            ])
            
            if explicit_detail:
                verbosity_directive = (
                    "RESPONSE LENGTH: The user explicitly asked for a detailed answer. "
                    "Provide a thorough, comprehensive response with full explanations, examples, and context. "
                    "Use clear section headers and bullet points for readability."
                )
            elif not vocalize:
                # Chat input — user is typing, probably wants a reasonably detailed answer
                verbosity_directive = (
                    "RESPONSE LENGTH: The user typed this in chat. Provide a moderately detailed answer — "
                    "enough to be genuinely useful (e.g. top 3-5 recommendations with a sentence each) "
                    "but don't write an essay. Aim for 4-8 sentences or a short list."
                )
            else:
                # Voice input — user is speaking, wants a concise spoken answer
                verbosity_directive = (
                    "RESPONSE LENGTH: The user SPOKE this via voice. Keep your response SHORT and conversational — "
                    "2-3 sentences max for simple questions, 4-5 sentences for knowledge questions. "
                    "No long lists, no essay-style paragraphs. Be direct and useful. "
                    "If the topic needs more detail, give the top 2-3 items and offer to elaborate."
                )

            response_policy_block = (
                "========================\n"
                "2. RESPONSE POLICY\n"
                "========================\n"
                "• Respond in natural, conversational plain text. Never wrap responses in curly braces or brackets.\n"
                "• Be warm but concise. You're a daily companion, not a corporate assistant.\n"
                "• HONESTY & TRANSPARENCY: If you genuinely cannot do something, say so clearly and explain why. \n"
                "  For example: 'I can't see your screen in real-time, but I can take a screenshot to check — want me to?'\n"
                "  Never pretend you did something you didn't. Never fabricate results.\n"
                "• ATTRIBUTION: Distinguish between OBSERVED USER WORK and REQUESTED ASSISTANT WORK.\n"
                "  When asked 'What was I doing?', say 'You were working on...' not 'I was working on...'.\n"
                "• GROUNDING: Distinguish between FACTS (directly observed telemetry) and INFERENCES.\n"
                "  If you don't have enough context, say 'I don't have enough context for that' rather than guessing.\n"
                "• CORRECTIONS: If the user says 'no', they're usually correcting a misunderstanding. \n"
                "  Don't execute the correction as a new command.\n"
                f"• {verbosity_directive}\n"
                "• When explaining yourself to new users ('what can you do?'), give a thorough answer with concrete examples.\n"
                "• Keep markdown minimal in spoken responses. Use it only for code blocks if sharing code."
            )

            memory_context = ""
            if hasattr(self._session, "_memory_runtime") and self._session._memory_runtime:
                memory_context = await self._session._memory_runtime.recall_context()
                
            workspace_summary = ""
            workspace_manager = getattr(self, '_workspace_manager', None) or getattr(self._session, 'workspace_manager', None) or getattr(self._context_synthesizer, 'workspace_manager', None)
            if workspace_manager:
                active_ws = workspace_manager.get_active_workspace()
                if active_ws and hasattr(active_ws, 'get_workspace_summary_prompt'):
                    workspace_summary = active_ws.get_workspace_summary_prompt()

            from arova.core.time import get_live_temporal_context_prompt
            import time as _time_mod
            last_accessed = None
            if hasattr(self._session, 'get_previous_user_turn_timestamp'):
                last_accessed = self._session.get_previous_user_turn_timestamp()
            if not last_accessed and workspace_manager:
                active_ws = workspace_manager.get_active_workspace()
                if active_ws:
                    last_accessed = active_ws.reality.last_accessed_at

            temporal_block = get_live_temporal_context_prompt(last_active_timestamp=last_accessed)
            if hasattr(self._session, '_persistent_last_active_ts'):
                self._session._persistent_last_active_ts = _time_mod.time()

            prompt_parts = [identity_block, response_policy_block, temporal_block]
            if workspace_summary:
                prompt_parts.append(workspace_summary)
            elif getattr(self._session, '_system_prompt', None):
                prompt_parts.append(f"========================\nOBSERVED CONTEXT\n========================\n{self._session._system_prompt}")
                
            if memory_context:
                prompt_parts.append(f"========================\n4. HISTORICAL MEMORY (Episodic Profile)\n========================\n{memory_context}")
                
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
            async for token in self._router.models.invoke_stream(messages, sys_prompt, depth=ReasoningDepth.STANDARD):
                full_text += token
                await buffer.append(token)
                
            await buffer.close()
            
            exec_meta = {}
            if hasattr(self._router, 'models') and hasattr(self._router.models, 'router'):
                exec_meta = getattr(self._router.models.router, 'last_execution_metadata', {}) or {}
                
            if hasattr(self, "_session") and self._session:
                self._session.add_assistant_message(full_text)
                
            # Signal EOF to TTSRuntime & Frontend
            logging.info(f"IntentRuntime: LLM stream complete. Emitting stream end for {turn_id}.")
            self._event_bus.emit("voice", "TEXT_RESPONSE_GENERATED", {
                "text": "",
                "turn_id": turn_id,
                "vocalize": vocalize,
                "execution_metadata": exec_meta
            })
        except Exception as e:
            logging.error(f"IntentRuntime: Error processing transcript: {e}", exc_info=True)
            error_msg = "I'm currently unable to connect to my cognitive providers. Please check the network or provider settings."
            if "offline" in str(e).lower():
                error_msg = "I'm currently unable to connect to my cognitive providers. Please check the network or provider settings."
            else:
                error_msg = "I encountered an unexpected error while processing that."
                
            self._event_bus.emit("voice", "TEXT_CHUNK_GENERATED", {
                "text": error_msg,
                "turn_id": turn_id,
                "vocalize": vocalize,
                "seq": 1
            })
            self._event_bus.emit("voice", "TEXT_RESPONSE_GENERATED", {
                "text": "",
                "turn_id": turn_id,
                "vocalize": vocalize,
                "execution_metadata": {}
            })
            if hasattr(self, "_session") and self._session:
                self._session.add_assistant_message(error_msg)
        finally:
            self._event_bus.emit("state", "EXECUTION_STATE_CHANGED", {"state": "COMPLETED", "turn_id": turn_id})
