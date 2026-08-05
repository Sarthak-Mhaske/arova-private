from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import uuid
from arova.core.models.runtime import ModelRuntime
from arova.core.models.schema import ReasoningDepth, ReasoningBudget
from arova.core.automation.graph import GraphDefinition, ExecutionNode
from arova.core.events import RuntimeEventBus, EventPayload

@dataclass
class IntentClassification:
    category: str # "action", "chat", "search", "ambient_reflex", "fast_action"
    confidence: float
    depth: ReasoningDepth
    fast_path_graph: Optional[GraphDefinition] = None
    reasoning: str = ""

class CognitiveRouter:
    """
    The Executive Function. Determines intent and reasoning depth.
    """
    def __init__(self, model_runtime: ModelRuntime, event_bus: RuntimeEventBus):
        self.models = model_runtime
        self.event_bus = event_bus

    def _build_fast_graph(self, name: str, capability: str, args: dict) -> GraphDefinition:
        node = ExecutionNode(id=str(uuid.uuid4()), capability_name=capability, args=args)
        return GraphDefinition(id=str(uuid.uuid4()), name=name, nodes=[node])

    def _get_fast_path(self, text: str) -> Optional[GraphDefinition]:
        """Deterministic regex/keyword bypass for maximum TTFA.
        This MUST be aggressive — the LLM fallback router is unreliable for action classification.
        BUT it must NOT false-positive on conversational mentions of keywords like 'video' or 'search'.
        """
        import re
        norm = text.lower().strip().strip(".!?")
        
        # If the text contains multiple intents, fallback to LLM Action Planner
        if any(w in norm for w in [" and ", " then ", ","]):
            return None
        
        # ── NEGATION / DISMISSAL GUARD ──
        # If user says "not", "don't", "aside", "leave", "ignore" about a topic, 
        # they're NOT requesting that action — they're explicitly rejecting it.
        negation_words = ["aside", "not ", "don't", "dont", "ignore", "skip", "leave", "leaving", "without", "other than", "besides", "except"]
        has_negation = any(w in norm for w in negation_words)
        
        # ── VOLUME CONTROL ──
        vol_match = re.search(r'(?:set\s+)?(?:vol(?:ume)?)\s*(?:to\s+)?(\d+)', norm)
        if vol_match:
            return self._build_fast_graph("Set Volume", "set_volume", {"level": int(vol_match.group(1))})
        
        if norm in ("mute", "unmute", "mute volume", "unmute volume"):
            level = 0 if "unmute" not in norm else 50
            return self._build_fast_graph("Set Volume", "set_volume", {"level": level})
        
        # ── MEDIA CONTROL ──
        if re.match(r'^(play|pause|stop|next|previous|skip|resume)\s*(music|track|song)?$', norm):
            if any(w in norm for w in ["next", "skip"]):
                cmd = "next_track"
            elif "previous" in norm:
                cmd = "previous_track"
            elif "stop" in norm:
                cmd = "stop"
            else:
                cmd = "play_pause"
            return self._build_fast_graph("Media Control", "media_control", {"command": cmd})
        
        if any(w in norm for w in ["play music", "play some music", "pause music", "stop music", "next track", "skip track", "previous track"]):
            if any(w in norm for w in ["next", "skip"]):
                cmd = "next_track"
            elif "previous" in norm:
                cmd = "previous_track"
            elif "stop" in norm:
                cmd = "stop"
            else:
                cmd = "play_pause"
            return self._build_fast_graph("Media Control", "media_control", {"command": cmd})
            
        # ── SCREENSHOT ──
        if any(w in norm for w in ["screenshot", "capture screen", "take a screenshot"]):
            return self._build_fast_graph("Take Screenshot", "screenshot", {})

        # ── SCREEN & VISION ANALYSIS ──
        # CRITICAL: Only trigger when user is ASKING ABOUT what's on their screen.
        # Do NOT match casual mentions of "video" or "yt" in conversation.
        # Guard: if the user has negation words ("leaving that video aside"), skip.
        if not has_negation:
            # High-confidence direct screen analysis phrases
            screen_direct = [
                "on my screen", "check my screen", "check screen", "analyze screen",
                "look at my screen", "what is on my screen", "what's on my screen",
                "video on my screen", "video i am watching", "video playing on my screen",
            ]
            if any(w in norm for w in screen_direct):
                return self._build_fast_graph("Analyze Screen", "analyze_screen", {"query": text})
            
            # Pattern: "is the/this video [on my screen] good/worth/..." — direct screen question
            if re.match(r'^(?:is\s+)?(?:the|this)\s+(?:youtube\s+|yt\s+)?video\s+(?:on\s+my\s+screen\s+)?(?:good|worth|useful|helpful|enough)', norm):
                return self._build_fast_graph("Analyze Screen", "analyze_screen", {"query": text})
            
            # Pattern: "check this/the video" (imperative, about the current screen)
            if re.match(r'^check\s+(?:this|the)\s+(?:youtube\s+|yt\s+)?video', norm):
                return self._build_fast_graph("Analyze Screen", "analyze_screen", {"query": text})

        # ── WORKSPACE RESTORE ──
        if norm in ["restore apps", "restore the apps", "restore workspace", "reopen workspace", "restore environment", "open apps", "restore my apps", "open all apps"]:
            return self._build_fast_graph("Restore Environment", "restore_environment", {"restore_all": True})

        # ── WEB SEARCH ──
        # Pronoun guard: if the captured query is just a pronoun, fall through to LLM
        # so it can resolve "it"/"that"/"this" from conversation history.
        PRONOUNS = {"it", "that", "this", "them", "those", "these", "him", "her", "one",
                     "it for me", "that for me", "this for me", "them for me", "it up", "that up"}
        
        search_query = None
        
        # Pattern group 1: "search google for X", "search web for X", "search for X"
        for prefix in ["search google for ", "google search ", "search web for ", "search the web for ", "search for "]:
            if norm.startswith(prefix):
                search_query = norm[len(prefix):].strip()
                break
        
        # Pattern group 2: "search X on google", "find X on google", "look up X on google"
        if not search_query:
            m = re.match(r'(?:search|find|look\s*up)\s+(.+?)\s+on\s+google', norm)
            if m:
                search_query = m.group(1).strip()
        
        # Pattern group 3: "google X" (e.g. "google weather in tokyo")
        if not search_query:
            m = re.match(r'^google\s+(.+)', norm)
            if m:
                search_query = m.group(1).strip()
        
        # Pattern group 4: "search X" (catch-all, e.g. "search weather in tokyo")
        if not search_query:
            m = re.match(r'^search\s+(.+)', norm)
            if m:
                search_query = m.group(1).strip()
        
        # Pattern group 5: "look up X", "find X" (without "on google")
        if not search_query:
            m = re.match(r'^(?:look\s*up|find)\s+(.+)', norm)
            if m:
                candidate = m.group(1).strip()
                if len(candidate.split()) >= 2 or any(w in candidate for w in ["news", "weather", "price", "score", "result", "update"]):
                    search_query = candidate
        
        # Pattern group 6: "find on google", "search on google" (no query)
        if not search_query:
            if re.match(r'^(?:find|search|look)\s+(?:on|in|with)\s+(?:google|the\s+web|browser|brave|chrome)', norm):
                # Fall through to LLM to resolve from conversation context
                return None
        
        if search_query:
            # PRONOUN GUARD: if query is just a pronoun, fall through to LLM ActionPlanner
            # which has conversation history and can resolve "search it" -> the actual topic
            if search_query.strip() in PRONOUNS:
                return None  # Let LLM resolve from conversation context
            return self._build_fast_graph("Web Search", "search_web", {"query": search_query})

        # ── APP LAUNCH ──
        app_match = re.match(r'^(?:can\s+you\s+)?(?:open(?:\s+up)?|launch|start|fire\s+up|run)\s+(.+)', norm)
        if app_match:
            app = app_match.group(1).strip()
            # Don't match pronouns — need LLM to resolve "open it", "open that"
            if app and app not in ("it", "that", "this", "the", "a", "one"):
                return self._build_fast_graph("Launch App", "open_app", {"app_name": app})

        return None

    def _emit_state(self, state: str, details: str = ""):
        self.event_bus.emit("cognition", "COGNITION_STATE_CHANGED", {
            "state": state,
            "details": details
        })

    async def route(self, messages: List[Dict[str, Any]]) -> IntentClassification:
        self._emit_state("ANALYZING_INTENT", "Checking fast-paths...")
        latest = [m["content"] for m in reversed(messages) if m["role"] == "user"]
        if not latest:
            return IntentClassification("chat", 1.0, ReasoningDepth.FAST)
            
        text = latest[0]
        norm = text.lower().strip().strip(".!?")
        
        # Check message history for screen analysis follow-up context (e.g. user says "yes" or "take a screenshot")
        prev_asst_msgs = [m["content"].lower() for m in reversed(messages[:-1]) if m["role"] == "assistant"]
        if prev_asst_msgs:
            last_asst = prev_asst_msgs[0]
            if any(w in last_asst for w in ["screenshot", "screen", "video", "check"]):
                if norm in ["yes", "yeah", "yep", "sure", "do it", "go ahead", "ok", "okay", "take screenshot", "take a screenshot", "take ss", "check it", "please do"]:
                    query = "Analyze the video and content on the screen to answer the user's question."
                    return IntentClassification(
                        category="fast_action",
                        confidence=1.0,
                        depth=ReasoningDepth.FAST,
                        fast_path_graph=self._build_fast_graph("Analyze Screen", "analyze_screen", {"query": query}),
                        reasoning="Follow-up affirmation for screen analysis."
                    )

        # 1. Attempt Fast Path (Zero-Shot Deterministic Bypass)
        fast_graph = self._get_fast_path(text)
        if fast_graph:
            self._emit_state("EXECUTING_FAST_PATH", f"Matched route: {fast_graph.name}")
            return IntentClassification(
                category="fast_action", 
                confidence=1.0, 
                depth=ReasoningDepth.FAST, 
                fast_path_graph=fast_graph,
                reasoning="Matched fast-path heuristic."
            )

        self._emit_state("CLASSIFYING_INTENT", "Consulting LLM router...")
        # 2. Fast LLM Routing (Determine if we need deep planning)
        sys_prompt = (
            "You are the Cognitive Router for Arova, an ambient desktop operating system with REAL system access.\n"
            "Arova can: open apps, search the web, control media, set volume, run commands.\n"
            "\n"
            "Categorize the user's intent into EXACTLY ONE of the following:\n"
            "- restore_workspace: The user wants to restore, reopen, or resume their workspace apps, files, project, or context.\n"
            "- action: The user wants you to PHYSICALLY DO something on their computer RIGHT NOW.\n"
            "  Examples of 'action': 'open brave', 'search google for X', 'play music', 'set volume to 50', 'take screenshot',\n"
            "  'check my screen', 'open youtube.com', 'run this command', 'close that app'.\n"
            "  Rules:\n"
            "  1. Direct OS commands ('open X', 'search X', 'play music', 'set volume') = action.\n"
            "  2. Follow-ups like 'do it', 'yes', 'go ahead' after an action context = action.\n"
            "  3. Multi-step commands ('open X and Y') = action.\n"
            "  4. Screen/video analysis requests ('is this video good', 'check my screen') = action.\n"
            "- chat: The user is asking a QUESTION, requesting ADVICE, or having a CONVERSATION.\n"
            "  Examples of 'chat': 'recommend some YouTubers', 'what are good resources to learn Python',\n"
            "  'can you make a learning roadmap for me', 'what if I watch X first then Y', 'tell me about X',\n"
            "  'explain how Y works', 'what are the best channels', 'give me a study plan',\n"
            "  'hello', 'what can you do', any knowledge/advice/recommendation question.\n"
            "  CRITICAL: If the user asks 'tell me good resources' or 'recommend channels', that is 'chat' NOT 'action'.\n"
            "  The user is asking for INFORMATION, not asking you to open apps.\n"
            "- deep_planning: Requires multi-step execution, heavy memory recall, or complex orchestration.\n"
            "Return JSON matching: {\"category\": \"...\", \"confidence\": 0.0-1.0, \"reasoning\": \"...\"}"
        )
        
        budget = ReasoningBudget(max_tokens=200)
        res = await self.models.invoke_structured(
            messages=messages, 
            system_prompt=sys_prompt, 
            depth=ReasoningDepth.FAST, 
            budget=budget
        )
        
        cat = res.get("category", "chat")
        conf = float(res.get("confidence", 0.5))
        reason = res.get("reasoning", "Failed to parse reasoning")
        
        if cat == "deep_planning":
            depth = ReasoningDepth.DEEP
            cat = "action" # deep planning resolves to actions eventually
            self._emit_state("DEEP_PLANNING_REQUIRED", "Routing to Context Synthesizer")
        else:
            depth = ReasoningDepth.STANDARD
            self._emit_state("STANDARD_ROUTING", f"Intent classified as: {cat}")

        return IntentClassification(
            category=cat,
            confidence=conf,
            depth=depth,
            reasoning=reason
        )
