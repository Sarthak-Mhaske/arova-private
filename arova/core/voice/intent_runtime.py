import logging
import os
import re
import webbrowser
import subprocess
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from arova.core.events import RuntimeEventBus
import asyncio
from arova.core.models.schema import ReasoningDepth, ReasoningBudget
from arova.core.cognition.router import CognitiveRouter
from arova.core.cognition.context import ContextSynthesizer
from arova.core.cognition.planner import CognitivePlanner
from arova.core.cognition.buffer import AsyncDeltaBuffer
from arova.core.time import get_live_temporal_context_prompt
from arova.core.tools.web_search import strip_emojis

# URLs and named study resources from assistant replies
_URL_RE = re.compile(r"https?://[^\s\)\]\>\"']+", re.IGNORECASE)
_NAMED_RESOURCE_URLS = {
    "3blue1brown": "https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab",
    "3b1b": "https://www.youtube.com/playlist?list=PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab",
    "gilbert strang": "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/",
    "strang": "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/",
    "mit opencourseware": "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/",
    "mit ocw": "https://ocw.mit.edu/courses/18-06-linear-algebra-spring-2010/",
    "introduction to linear algebra": "https://math.mit.edu/~gs/linearalgebra/",
    "khan academy linear algebra": "https://www.khanacademy.org/math/linear-algebra",
    "khan academy": "https://www.khanacademy.org/math/linear-algebra",
}

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
                 action_planner: Any = None):
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
        Receives final transcripts and parses them — now with @-mention grounding.
        """
        transcript = payload.transcript if hasattr(payload, 'transcript') else payload.get("transcript", "") if isinstance(payload, dict) else str(payload)
        turn_id = getattr(payload, "turn_id", None)
        if turn_id is None and isinstance(payload, dict):
            turn_id = payload.get("turn_id")
        elif turn_id is None and hasattr(payload, 'data') and isinstance(payload.data, dict):
            turn_id = payload.data.get("turn_id")
        source = getattr(payload, "source", "text") if hasattr(payload, "source") else payload.get("source", "text") if isinstance(payload, dict) else "text"
        
        # Default vocalize: True ONLY if input source is voice/mic/stt, False for typed chat/UI
        is_voice_source = source in ("voice", "wake_word", "stt", "mic")
        default_vocalize = True if is_voice_source else False
        
        vocalize = getattr(payload, "vocalize", default_vocalize)
        if isinstance(payload, dict) and "vocalize" in payload:
            vocalize = bool(payload["vocalize"])
        elif hasattr(payload, 'data') and isinstance(payload.data, dict) and "vocalize" in payload.data:
            vocalize = bool(payload.data["vocalize"])
            
        if is_voice_source:
            vocalize = True
        elif source in ("text", "ui", "chat", "command_palette") and not (isinstance(payload, dict) and payload.get("vocalize") is True):
            vocalize = False

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

    # ------------------------------------------------------------------
    # Open prior resources (from last assistant message)
    # ------------------------------------------------------------------
    def _extract_urls_from_text(self, text: str) -> List[str]:
        if not text:
            return []
        found = _URL_RE.findall(text)
        cleaned = []
        for u in found:
            u = u.rstrip(".,;:)]}'\"")
            if u and u not in cleaned:
                cleaned.append(u)
        return cleaned

    def _extract_named_resource_urls(self, text: str) -> List[str]:
        if not text:
            return []
        lower = text.lower()
        urls: List[str] = []
        for name in sorted(_NAMED_RESOURCE_URLS.keys(), key=len, reverse=True):
            if name in lower:
                url = _NAMED_RESOURCE_URLS[name]
                if url not in urls:
                    urls.append(url)
        return urls

    def _open_url(self, url: str) -> bool:
        """Best-effort open URL in default browser. Never raises."""
        try:
            if os.name != "nt":
                try:
                    subprocess.Popen(
                        ["xdg-open", url],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    return True
                except FileNotFoundError:
                    pass
            webbrowser.open(url)
            return True
        except Exception as e:
            logging.warning(f"IntentRuntime: failed to open url {url}: {e}")
            return False

    async def _handle_open_prior_resources(self, transcript: str, turn_id: str, vocalize: bool = True):
        """Open URLs / named resources from the last assistant message. Never launch snap."""
        logging.info("IntentRuntime: open_prior_resources path")
        last = ""
        try:
            if self._session:
                last = self._session.last_assistant_message() or ""
        except Exception:
            last = ""

        urls = self._extract_urls_from_text(last)
        if not urls:
            urls = self._extract_named_resource_urls(last)
        urls = urls[:5]

        self._event_bus.emit("voice", "TEXT_STREAM_STARTED", {"turn_id": turn_id})

        if not urls:
            msg = (
                "I don't see any openable links in my last reply. "
                "Ask me for resources again and I'll include direct URLs, then say open these."
            )
            self._event_bus.emit("voice", "TEXT_CHUNK_GENERATED", {
                "text": msg, "turn_id": turn_id, "vocalize": vocalize, "seq": 1
            })
            self._event_bus.emit("voice", "TEXT_RESPONSE_GENERATED", {
                "text": msg, "turn_id": turn_id, "vocalize": vocalize
            })
            if self._session:
                self._session.add_assistant_message(msg)
            return

        opened, failed = [], []
        for u in urls:
            if self._open_url(u):
                opened.append(u)
            else:
                failed.append(u)

        if opened and not failed:
            msg = f"Opened {len(opened)} resource{'s' if len(opened) != 1 else ''} in your browser."
        elif opened and failed:
            msg = f"Opened {len(opened)}, but couldn't open {len(failed)}."
        else:
            msg = "I found links but couldn't open them from this environment. Here they are:\n" + "\n".join(urls)

        if opened:
            msg = f"{msg}\n" + "\n".join(f"• {u}" for u in opened)

        self._event_bus.emit("voice", "TEXT_CHUNK_GENERATED", {
            "text": msg, "turn_id": turn_id, "vocalize": vocalize, "seq": 1
        })
        self._event_bus.emit("voice", "TEXT_RESPONSE_GENERATED", {
            "text": msg, "turn_id": turn_id, "vocalize": vocalize
        })
        if self._session:
            self._session.add_assistant_message(msg)

    async def _process_transcript_cognition(self, transcript: str, turn_id: str, vocalize: bool = True, mentions: list = None):
        logging.info(f"IntentRuntime: _process_transcript_cognition entered. transcript='{transcript}', turn_id={turn_id}")
        self._event_bus.emit("state", "EXECUTION_STATE_CHANGED", {"state": "THINKING", "turn_id": turn_id})
        try:
            # Phase 2: Trigger memory ghost recall asynchronously before responding
            if hasattr(self._session, "_memory_runtime") and self._session._memory_runtime:
                try:
                    await self._session._memory_runtime.recall_ghosts_for_transcript(transcript)
                except Exception as e:
                    logging.debug(f"IntentRuntime: memory recall skipped: {e}")
            
            # 1. Update existing turn transcript or start new turn if needed
            if turn_id and self._session.is_authoritative(turn_id):
                self._session.update_active_user_transcript(transcript)
            else:
                turn = self._session.start_new_turn(transcript)
                turn_id = turn.turn_id

            if self._event_bus:
                self._event_bus.emit("timeline", "create", {
                    "category": "cognition",
                    "title": f"Prompt: {transcript[:50]}",
                    "description": transcript,
                    "source": "user",
                    "importance": 0.6,
                    "correlation_id": turn_id,
                    "metadata": {"vocalize": vocalize, "transcript": transcript}
                })

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

            # 3. Single route call with light context history
            messages = self._session.build_api_messages(max_turns=4)
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

            # --- Open resources mentioned in the previous assistant turn ---
            if (
                intent_class.category == "open_prior_resources"
                or getattr(intent_class, "action_hint", None) == "open_prior_resources"
            ):
                await self._handle_open_prior_resources(transcript, turn_id, vocalize)
                return

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
                            
                        # Check if any action node produced rich informational analysis output
                        info_output = None
                        search_output = None
                        for res in results:
                            if isinstance(res, dict) and res.get("status") == "success":
                                cap = res.get("capability", "")
                                out = res.get("output", "")
                                if cap in ("analyze_screen", "read_file") and out and len(out) > 40:
                                    info_output = out
                                    break
                                elif cap == "search_web" and out:
                                    search_output = out
                                    
                        final_msg = ""
                        if info_output:
                            # Preserve the full, detailed rich markdown analysis from vision/file tools for the UI
                            final_msg = info_output.strip()
                        else:
                            # Generate refined LLM response that directly answers the user's prompt & summarizes actions
                            user_home = os.path.expanduser("~")
                            search_context = f"\n\nLIVE WEB SEARCH RESULTS:\n{search_output}\nUse these live web search results above to answer accurately, factually, and with source citations.\n" if search_output else ""
                            prompt = (
                                f"The user asked: '{transcript}'.\n"
                                f"I executed these background actions for them: {results}.{search_context}\n"
                                "Instructions:\n"
                                "1. If the user asked a question or wanted advice, a roadmap, recommendations, or search results, ANSWER THEM directly, completely, and accurately.\n"
                                "2. STRICT ANTI-EMOJI RULE: NEVER output emojis under any circumstances (no 📚, 🎨, 🤖, 📦, 🔍, 🚀, 💡, ⚡, etc.). Maintain clean, dense, minimalist markdown typography.\n"
                                "3. If live search results were provided above, synthesize them into a concise, well-structured response citing key information.\n"
                                "4. Briefly mention what actions were taken for them (e.g. 'I searched the web for the latest models').\n"
                                f"5. EXPLICIT FOLDER / PATH MENTION: If a folder, directory, file, or project was created or opened, EXPLICITLY state its exact real path e.g. '{user_home}/PythonLearning' or '~/PythonLearning'. NEVER use fake paths like '/home/user'.\n"
                                "6. FORMATTING RULE: Do NOT wrap URLs or file paths in broken bold asterisks `**` across line breaks. Write URLs as plain `https://...` or standard markdown links [text](url). Write file paths in plain text or code ticks e.g. `~/PythonLearning`.\n"
                                "7. Respond in natural conversational text without emojis."
                            )
                            try:
                                final_msg = await self._router.models.generate(
                                    messages=messages + [{"role": "user", "content": prompt}],
                                    system_prompt="You are Arova, a precise AI assistant. Give a direct, accurate answer. NEVER use emojis. Do not claim capabilities you lack.",
                                    depth=ReasoningDepth.STANDARD,
                                    budget=ReasoningBudget(max_tokens=1024)
                                )
                            except Exception as e:
                                logging.error(f"Failed to generate refined response: {e}")
                                if success:
                                    if search_output:
                                        final_msg = f"Here are the live search results for your query:\n\n{search_output}"
                                    elif graph and hasattr(graph, 'name') and graph.name:
                                        final_msg = f"Done. I've completed: {graph.name}."
                                    elif feedback_message and feedback_message != "Executing action...":
                                        final_msg = f"Done. {feedback_message}"
                                    else:
                                        final_msg = "Done. I've executed the requested actions."
                                else:
                                    final_msg = "I attempted the action, but it didn't complete successfully. Let me know if you'd like me to try again."
                        final_msg = strip_emojis(final_msg.strip())
                            
                    except asyncio.TimeoutError:
                        final_msg = "The action is taking longer than expected, but it is running in the background."
                    finally:
                        self._pending_executions.pop(turn_id, None)
                    
                    self._event_bus.emit("state", "EXECUTION_STATE_CHANGED", {"state": "IDLE", "turn_id": turn_id})
                    
                    if self._event_bus:
                        # Build interactive action pills for suggestions or permission requests
                        actions = []
                        results_str = str(results)
                        if "YouTube Music Desktop App is not installed" in results_str:
                            actions = [
                                {
                                    "label": "Install YT Music App",
                                    "primary": True,
                                    "eventType": "user.message",
                                    "eventPayload": {"text": "install youtube music app", "vocalize": True}
                                },
                                {
                                    "label": "Keep Playing in Browser",
                                    "primary": False,
                                    "eventType": "user.message",
                                    "eventPayload": {"text": "keep using browser for music", "vocalize": False}
                                }
                            ]
                        elif "close_app" in results_str or "close_window" in results_str:
                            actions = [
                                {
                                    "label": "Undo / Reopen App",
                                    "primary": False,
                                    "eventType": "user.message",
                                    "eventPayload": {"text": "reopen app", "vocalize": False}
                                }
                            ]

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
                            "actions": actions,
                            "seq": 2
                        })
                        self._event_bus.emit("voice", "TEXT_RESPONSE_GENERATED", {"turn_id": turn_id, "text": final_msg, "actions": actions})
                        self._event_bus.emit("timeline", "create", {
                            "category": "routing",
                            "title": "Executed System Action",
                            "description": final_msg[:120],
                            "source": "action_dispatcher",
                            "importance": 0.7,
                            "correlation_id": turn_id,
                            "metadata": {"results": str(results)[:200]}
                        })
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
            
            # ── COMPACT IDENTITY (token-optimized) ──
            # Only expand capabilities when user explicitly asks
            _intro_keywords = ["what can you do", "what are you", "who are you", "your capabilities",
                               "what do you do", "tell me about yourself", "help me understand",
                               "introduce yourself", "what is arova"]
            _wants_intro = any(kw in transcript.lower() for kw in _intro_keywords)

            if _wants_intro:
                identity_block = (
                    "You are Arova — an intelligent AI assistant and thinking partner.\n\n"
                    "ACTUAL CAPABILITIES (only claim what is listed here):\n"
                    "- Conversational intelligence: discuss ideas, answer questions, brainstorm, explain concepts\n"
                    "- Code assistance: write code, debug errors, explain algorithms, review code\n"
                    "- Web search: find information online when asked\n"
                    "- Terminal commands: run shell commands when the user requests system actions\n"
                    "- Workspace context: when configured, you receive context about the user's active project files and recent activity\n"
                    "- Memory: when enabled, remember user preferences and past conversations\n\n"
                    "STRICT HONESTY RULES:\n"
                    "- NEVER claim you can see the user's desktop, open windows, monitor layout, or screen content unless that data is explicitly provided in the OBSERVED CONTEXT block below.\n"
                    "- NEVER claim you can read the clipboard or selected text unless clipboard data is explicitly provided.\n"
                    "- NEVER claim you can rearrange windows, create virtual desktops, or manage window layouts.\n"
                    "- NEVER list capabilities you do not actually have. If you are unsure whether you can do something, say so.\n"
                    "- Only describe capabilities that are grounded in actual data provided to you in this prompt.\n"
                    "- Be direct, natural, and conversational. Do not over-explain or pad responses."
                )
            else:
                identity_block = (
                    "You are Arova — an intelligent AI assistant and thinking partner. "
                    "You can discuss any topic, write and debug code, answer questions, brainstorm ideas, run terminal commands, and search the web. "
                    "STRICT HONESTY: NEVER claim capabilities you do not have. Do NOT claim you can see the desktop, read clipboard, rearrange windows, or observe open applications unless that data is explicitly provided below. "
                    "Be helpful, intelligent, direct, and conversational. Do not fabricate or exaggerate your capabilities."
                )

            # ── DYNAMIC INTENT & RELEVANCE ANALYZER ──
            lower_transcript = transcript.lower()
            explicit_detail = any(w in lower_transcript for w in [
                "in depth", "in detail", "detailed", "thorough", "comprehensive", 
                "explain in detail", "elaborate", "tell me everything", "full explanation",
                "deep dive", "tell me all"
            ])

            # Dynamically determine if workspace/memory context is actually relevant to the user query
            is_workspace_relevant = any(w in lower_transcript for w in [
                "file", "code", "workspace", "project", "repo", "git", "commit", "working on",
                "edit", "function", "class", "bug", "terminal", "log", "error", "build", "script",
                "folder", "path", "directory", "arova", "readme"
            ])
            
            is_memory_relevant = is_workspace_relevant or any(w in lower_transcript for w in [
                "remember", "recall", "memory", "prefer", "like", "favorite", "last time", "before", "history",
                "who am i", "my name", "what do i"
            ])

            if explicit_detail:
                verbosity_directive = (
                    "RESPONSE STYLE: The user requested an in-depth response. "
                    "Provide a thorough, comprehensive explanation with clear structure and necessary detail."
                )
            elif not vocalize:
                # Chat input
                verbosity_directive = (
                    "RESPONSE STYLE: Text chat mode. Provide a clear, moderately detailed answer "
                    "useful for reading on screen."
                )
            else:
                # Spoken voice mode
                verbosity_directive = (
                    "SPOKEN VOICE MODE: The user is communicating via microphone. "
                    "Adapt your response dynamically to sound like a natural human voice partner:\n"
                    "• For actions & system commands (e.g. closing windows, playing music): State a brief, natural confirmation of the action.\n"
                    "• For quick questions (e.g. time, weather, facts): Answer directly and conversationally.\n"
                    "• For complex inquiries: Give the core answer clearly, avoiding markdown tables or bulleted lists that sound awkward when read aloud.\n"
                    "• Never include unsolicited disclaimers or background summaries of unrelated context.\n"
                    "• NEVER speak raw http/https URLs aloud. Refer to apps, websites, or tools naturally by name (e.g. 'on YouTube Music', 'on GitHub')."
                )

            url_policy = "• NEVER output raw URLs in spoken voice mode." if vocalize else "• Include full https:// URLs when recommending web resources."
            response_policy_block = (
                "RESPONSE POLICY:\n"
                "• ABSOLUTE EMOJI BAN: You must NEVER use ANY emoji characters whatsoever. No unicode pictographs, no emoticons, no symbols like stars/arrows/checkmarks from emoji ranges. Zero tolerance. This includes but is not limited to: no folder icons, no clipboard icons, no tool icons, no rocket ships, no light bulbs, no sparkles, no warning signs, no checkmarks, no crosses, no stars, no arrows, no pointing hands, no globes, no books, no gears, no fire, no hearts. Use plain text, dashes, and markdown formatting only.\n"
                "• Natural, authentic conversational style. Daily intelligent partner, not corporate assistant.\n"
                "• HONESTY FIRST: Never fabricate results, never pretend you performed actions you didn't, never claim capabilities you lack. If context data (desktop, clipboard, files) is not provided in this prompt, do NOT pretend you have it.\n"
                "• Do not say 'I am a large language model'. Identify as Arova when asked.\n"
                "• Distinguish observed user work vs your own: 'You were working on...' not 'I was working on...'\n"
                f"• {verbosity_directive}\n"
                f"{url_policy}"
            )

            memory_context = ""
            if is_memory_relevant and hasattr(self._session, "_memory_runtime") and self._session._memory_runtime:
                memory_context = await self._session._memory_runtime.recall_context()
                
            workspace_summary = ""
            if is_workspace_relevant:
                workspace_manager = getattr(self, '_workspace_manager', None) or getattr(self._session, 'workspace_manager', None) or getattr(self._context_synthesizer, 'workspace_manager', None)
                if workspace_manager:
                    active_ws = workspace_manager.get_active_workspace()
                    if active_ws and hasattr(active_ws, 'get_workspace_summary_prompt'):
                        workspace_summary = active_ws.get_workspace_summary_prompt()

            import time as _time_mod
            last_accessed = None
            if hasattr(self._session, 'get_previous_user_turn_timestamp'):
                last_accessed = self._session.get_previous_user_turn_timestamp()
            if not last_accessed and is_workspace_relevant and workspace_manager:
                active_ws = workspace_manager.get_active_workspace()
                if active_ws:
                    last_accessed = active_ws.reality.last_accessed_at

            temporal_block = get_live_temporal_context_prompt(last_active_timestamp=last_accessed)
            if hasattr(self._session, '_persistent_last_active_ts'):
                self._session._persistent_last_active_ts = _time_mod.time()
                
            grounded_block = ""
            if is_workspace_relevant:
                try:
                    cognitive_context = await self._context_synthesizer.synthesize(transcript, mentions=mentions or [])
                    grounded_block = cognitive_context.to_system_prompt_block() if cognitive_context else ""
                except Exception as e:
                    logging.warning(f"Grounded synthesis failed: {e}")

            prompt_parts = [identity_block, response_policy_block, temporal_block]
            
            if grounded_block:
                prompt_parts.append(grounded_block)
            elif workspace_summary:
                prompt_parts.append(workspace_summary)
            elif is_workspace_relevant and getattr(self._session, '_system_prompt', None):
                sys_ctx = self._session._system_prompt
                prompt_parts.append(f"========================\nOBSERVED CONTEXT\n========================\n{sys_ctx}")
                
            if memory_context:
                prompt_parts.append(f"RECALLED MEMORY:\n{memory_context}")
                
            # Limit conversation history for voice turns dynamically based on mode
            max_turns = 4 if vocalize and not explicit_detail else 6
            if len(messages) > max_turns:
                messages = messages[-max_turns:]

            # Filter out error/failure messages from history — they waste tokens and confuse context
            _error_phrases = ["unable to reach llm", "unable to connect", "no inference provider",
                              "encountered an unexpected error", "max retries exceeded", "connection refused"]
            messages = [
                m for m in messages
                if not (m.get("role") == "assistant" and any(ep in m.get("content", "").lower() for ep in _error_phrases))
            ]

            sys_prompt = "\n\n".join(prompt_parts)        
            # Stream chunks directly to TTS Runtime (Phase 7.5 streaming TTS)
            logging.info(f"IntentRuntime: Emitting stream start for {turn_id}")
            self._event_bus.emit("voice", "TEXT_STREAM_STARTED", {
                "turn_id": turn_id
            })
            
            collected_chunks = []
            async def _on_chunk_batch(text_chunk: str, seq: int):
                clean_chunk = strip_emojis(text_chunk)
                if not clean_chunk:
                    return
                logging.info(f"IntentRuntime: LLM batch seq {seq}: '{clean_chunk}'")
                collected_chunks.append(clean_chunk)
                self._event_bus.emit("voice", "TEXT_CHUNK_GENERATED", {
                    "text": clean_chunk,
                    "turn_id": turn_id,
                    "vocalize": vocalize,
                    "seq": seq
                })
                
            buffer = AsyncDeltaBuffer(_on_chunk_batch, flush_interval_s=0.05)
            
            # ── DYNAMIC COGNITIVE ROUTING ANALYZER ──
            # Determine reasoning depth based on prompt complexity, length, and task type
            prompt_len = len(transcript)
            lower_transcript = transcript.lower()
            complex_keywords = [
                "roadmap", "plan", "strategy", "priority", "schedule", "course", "hackathon",
                "explain", "analyze", "architecture", "design", "debug", "code", "algorithm",
                "dsa", "database", "system", "research", "exam", "assessment", "difference",
                "tradeoff", "deep dive", "step by step"
            ]
            is_complex_task = any(kw in lower_transcript for kw in complex_keywords) or prompt_len > 350

            if is_complex_task:
                target_depth = ReasoningDepth.DEEP
                token_budget = 4096
                logging.info(f"IntentRuntime: Route -> DEEP REASONING (len={prompt_len}, complex={is_complex_task})")
            elif prompt_len < 150 and not vocalize:
                target_depth = ReasoningDepth.FAST
                token_budget = 2048
                logging.info(f"IntentRuntime: Route -> FAST CHAT (len={prompt_len})")
            else:
                target_depth = ReasoningDepth.STANDARD
                token_budget = 4096
                logging.info(f"IntentRuntime: Route -> STANDARD CHAT (len={prompt_len})")

            stream_success = False
            try:
                async for token in self._router.models.invoke_stream(
                    messages, sys_prompt, depth=target_depth, budget=ReasoningBudget(max_tokens=token_budget)
                ):
                    await buffer.append(token)
                    stream_success = True
            except Exception as e:
                logging.warning(f"IntentRuntime LLM stream failed: {e}")
                stream_success = False
                
            await buffer.close()
            full_text = "".join(collected_chunks).strip()

            # === TIER 1 MOAT FALLBACK: If no tokens or provider error, synthesize grounded mock ===
            is_error_response = any(phrase in full_text.lower() for phrase in [
                "unable to connect", "no inference provider", "max retries exceeded",
                "connection refused", "encountered an unexpected error", "name 'os' is not defined",
            ])
            if is_error_response:
                # Drop error text so we don't stream "error + grounded" duplicate garbage
                logging.warning("IntentRuntime: clearing error provider text before grounded fallback")
                full_text = ""
                stream_success = False
            if not stream_success or not full_text or is_error_response:
                grounded = getattr(cognitive_context, 'grounded_resources', None) if 'cognitive_context' in locals() else None
                active_ws = None
                try:
                    wm = getattr(self, '_workspace_manager', None) or getattr(self._session, 'workspace_manager', None) or getattr(self._context_synthesizer, 'workspace_manager', None)
                    if wm:
                        active_ws = wm.get_active_workspace()
                except:
                    pass
                resume_intents = {"where was i?", "where was i", "what was i doing", "resume", "what's next", "whats next", "continue", "where did i leave off"}
                is_resume_query = transcript.strip().lower() in resume_intents or any(q in transcript.lower() for q in ["where was i", "what was i doing", "what was i working on", "where did i leave off"])
                if active_ws and is_resume_query:
                    title = getattr(active_ws, 'title', 'your workspace')
                    goal = getattr(active_ws.understanding.momentum, 'goal', 'continuing work') if hasattr(active_ws, 'understanding') else 'continuing work'
                    blocker = getattr(active_ws.understanding.momentum, 'current_blocker', None) if hasattr(active_ws, 'understanding') else None
                    nxt = getattr(active_ws.understanding.momentum, 'next_action', None) if hasattr(active_ws, 'understanding') else None
                    conf = getattr(active_ws.understanding.confidence, 'score', 0) if hasattr(active_ws, 'understanding') else 0
                    if conf is None:
                        conf = 0
                    hedge = "I think " if 0 < conf < 70 else ""
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
                    if 0 < conf < 70:
                        mock_answer += f" ({conf}% confidence — please verify)"
                    for chunk in [mock_answer[i:i+60] for i in range(0, len(mock_answer), 60)]:
                        await buffer.append(chunk)
                    full_text = mock_answer
                import re
                has_explicit_at_mention = bool(re.search(r'(?:\s|^)@[\w.-]+', transcript))
                if grounded and has_explicit_at_mention and cognitive_context and getattr(cognitive_context, 'mentioned_resources', None):
                    mock_answer = f"Got it — you @-mentioned a file. Here's the verbatim context I'm grounding on:\n\n{cognitive_context.mentioned_resources[:800]}\n\nBased on that, the issue is around the code above. Want me to trace the flow?"
                    for chunk in [mock_answer[i:i+60] for i in range(0, len(mock_answer), 60)]:
                        await buffer.append(chunk)
                    full_text = mock_answer
                else:
                    if not full_text.strip():
                        fallback = "Unable to reach LLM provider. Please check network connection or provider settings."
                        await buffer.append(fallback)
                        full_text = fallback

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
            if full_text and self._event_bus:
                self._event_bus.emit("timeline", "create", {
                    "category": "cognition",
                    "title": "Arova Response",
                    "description": full_text[:120] + ("..." if len(full_text) > 120 else ""),
                    "source": "model_runtime",
                    "importance": 0.5,
                    "correlation_id": turn_id,
                    "metadata": {"length": len(full_text)}
                })
        except Exception as e:
            logging.error(f"IntentRuntime: Error processing transcript: {e}", exc_info=True)
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
            self._event_bus.emit("cognition", "COGNITION_STATE_CHANGED", {"state": "IDLE", "details": ""})
