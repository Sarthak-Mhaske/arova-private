from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import uuid
from arova.core.models.runtime import ModelRuntime
from arova.core.models.schema import ReasoningDepth, ReasoningBudget
from arova.core.automation.graph import GraphDefinition, ExecutionNode
from arova.core.events import RuntimeEventBus, EventPayload

@dataclass
class IntentClassification:
    category: str # "action", "chat", "search", "ambient_reflex", "fast_action", "open_prior_resources"
    confidence: float
    depth: ReasoningDepth
    fast_path_graph: Optional[GraphDefinition] = None
    reasoning: str = ""
    action_hint: Optional[str] = None
    action_payload: Optional[Dict[str, Any]] = None

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

    def _get_fast_path(self, text: str, messages: Optional[List[Dict[str, Any]]] = None) -> Optional[GraphDefinition]:
        """Deterministic regex/keyword bypass for maximum TTFA.
        This MUST be aggressive — the LLM fallback router is unreliable for action classification.
        BUT it must NOT false-positive on conversational mentions of keywords like 'video' or 'search'.
        """
        import re
        norm = text.lower().strip().strip(".!?")
        
        # ── YOUTUBE SEARCH ACTION ──
        yt_match = re.match(r'^(?:can\s+you\s+)?(?:please\s+)?open\s+youtube[,\s]+(.+)', norm)
        if yt_match:
            yt_query = yt_match.group(1).strip()
            if yt_query:
                import urllib.parse
                yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(yt_query)}"
                return self._build_fast_graph("Open YouTube Search", "open_app", {"app_name": yt_url})

        # If the text contains multiple distinct sequential intents, fallback to LLM Action Planner
        if any(w in norm for w in [" and then ", " then "]):
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
        
        # ── MEDIA CONTROL & MUSIC PLAYBACK ──
        if re.match(r'^(pause|stop|next|previous|skip|resume)\s*(music|track|song|audio)?$', norm):
            if any(w in norm for w in ["next", "skip"]):
                cmd = "next_track"
            elif "previous" in norm:
                cmd = "previous_track"
            elif "stop" in norm:
                cmd = "stop"
            else:
                cmd = "play_pause"
            return self._build_fast_graph("Media Control", "media_control", {"command": cmd})

        # Matches "play some chill hindi song", "play starboy", "play lofi", "play arijit singh songs", "play that song", etc.
        play_match = re.match(r'^(?:can\s+you\s+)?(?:please\s+)?play\s+(?:some\s+|the\s+(?:song\s+|track\s+)?)?(.+)', norm)
        if play_match:
            raw_song = play_match.group(1).strip()
            # Strip trailing polite fluff
            raw_song = re.sub(r"\s+(?:please|for\s+me|thanks|thank\s+you)\s*$", "", raw_song).strip()
            
            if not raw_song or raw_song in ("music", "track", "song", "audio"):
                return self._build_fast_graph("Media Control", "media_control", {"command": "play_pause"})
            
            deictic_words = {
                "it", "that", "this", "them", "those", "these", "one", "that one", "this one",
                "that song", "tthat song", "this song", "the song", "the track", "that track",
                "those songs", "the one you said", "the one you mentioned", "the one you recommended",
                "the first one", "the second one", "the last one", "what you said", "what you recommended"
            }
            
            # If the query is complex, mood-based, lyrical, or descriptive -> let LLM ActionPlanner resolve dynamically
            dynamic_triggers = [
                "lyrics", "chill", "relaxing", "sad", "happy", "party", "lofi", "vibes",
                "mood", "instrumental", "romantic", "similar to", "like", "recommend",
                "something by", "some song", "any song", "whose", "called", "named"
            ]
            
            if any(dt in raw_song for dt in dynamic_triggers) or raw_song in deictic_words:
                # Let ActionPlanner LLM resolve it with full world knowledge & conversation history
                return None
            
            clean_query = re.sub(r'^(?:song|songs|track|tracks|music)\s+(?:of\s+|by\s+)?', '', raw_song).strip()
            song_query = clean_query if clean_query else raw_song
            return self._build_fast_graph(f"Play {song_query}", "play_music", {"song_query": song_query})
            
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
        
        # Pattern group 1: "search google for X", "search web for X", "search for X", "find for X", "do google search for X"
        for prefix in [
            "do a google search for ", "do google search for ", "google search for ", "google search ",
            "search google for ", "search web for ", "search the web for ", "search for ",
            "find for list of ", "find list of ", "find for ", "find me "
        ]:
            if norm.startswith(prefix):
                search_query = norm[len(prefix):].strip()
                break
        
        # Pattern group 2: "search X on google", "find X on google", "look up X on google"
        if not search_query:
            m = re.match(r'(?:search|find|look\s*up|do\s+a\s+search\s+for|do\s+google\s+search\s+for)\s+(.+?)\s+on\s+google', norm)
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
                if len(candidate.split()) >= 2 or any(w in candidate for w in ["news", "weather", "price", "score", "result", "update", "latest", "models", "list"]):
                    search_query = candidate
        
        # Pattern group 6: "do google search", "do a google search", "search google", "find on google", "search on google"
        if not search_query:
            if re.match(r'^(?:do\s+(?:a\s+)?google\s+search|do\s+search|search\s+google|google\s+it|search\s+it|find|search|look)\s*(?:on|in|with)?\s*(?:google|the\s+web|browser|brave|chrome)?$', norm):
                if messages and len(messages) >= 2:
                    for prev_msg in reversed(messages[:-1]):
                        if prev_msg.get("role") == "user" and prev_msg.get("content"):
                            prev_content = prev_msg.get("content").strip()
                            if len(prev_content) > 3 and not re.match(r'^(?:do\s+google\s+search|yes|no|ok|sure|thanks)$', prev_content.lower()):
                                search_query = prev_content
                                break
                if not search_query:
                    # Fall through to LLM ActionPlanner to resolve from conversation context
                    return None
        
        if search_query:
            # PRONOUN GUARD: if query is just a pronoun, fall through to LLM ActionPlanner
            # which has conversation history and can resolve "search it" -> the actual topic
            if search_query.strip() in PRONOUNS:
                return None  # Let LLM resolve from conversation context
            return self._build_fast_graph("Web Search", "search_web", {"query": search_query})

        # ── OPEN PRIOR RESOURCES (links from last assistant message) ──
        # "open these resources for me" must NEVER become open_app("these resources...")
        # which previously launched /bin/snap with score 60.
        open_prior_pats = [
            r"\bopen\s+(these|those|the|that|this)\s+(resources?|links?|urls?|tabs?|pages?|docs?|sites?)\b",
            r"\bopen\s+(the\s+)?(resources?|links?|urls?)\s+(for\s+me|please)?\b",
            r"\b(can\s+you\s+)?open\s+(them|those|these)\b",
            r"\blaunch\s+(these|those|the)\s+(resources?|links?|urls?)\b",
        ]
        for pat in open_prior_pats:
            if re.search(pat, norm):
                # Signal via special graph name — IntentRuntime handles open_prior_resources
                return self._build_fast_graph(
                    "Open Prior Resources",
                    "open_prior_resources",
                    {},
                )

        # ── YOUTUBE SEARCH ACTION ──
        yt_match = re.match(r'^(?:can\s+you\s+)?(?:please\s+)?open\s+youtube[,\s]+(.+)', norm)
        if yt_match:
            yt_query = yt_match.group(1).strip()
            if yt_query:
                import urllib.parse
                yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(yt_query)}"
                return self._build_fast_graph("Open YouTube Search", "open_app", {"app_name": yt_url})

        # ── APP LAUNCH ──
        # Only known desktop apps. Reject multi-word deictic garbage.
        KNOWN_APPS = {
            "kitty", "brave", "firefox", "chrome", "chromium", "spotify", "code",
            "vscode", "cursor", "slack", "discord", "telegram", "obsidian", "notion",
            "terminal", "gnome-terminal", "alacritty", "wezterm", "nautilus", "files",
            "calculator", "settings", "thunderbird", "zoom", "figma", "postman",
            "docker", "steam", "vlc", "mpv", "gedit", "nvim", "vim", "emacs",
            "edge", "opera", "arc", "youtube", "yt music", "youtube music",
        }
        DEICTIC = {
            "it", "that", "this", "the", "a", "an", "one", "them", "those", "these",
            "my", "your", "our", "some", "any", "all", "resources", "resource",
            "links", "link", "urls", "url", "tabs", "pages", "docs", "sites",
        }
        app_match = re.match(
            r'^(?:can\s+you\s+)?(?:please\s+)?(?:open(?:\s+up)?|launch|start|fire\s+up|run)\s+(.+)',
            norm,
        )
        if app_match:
            app = app_match.group(1).strip()
            # Strip trailing polite fluff
            app = re.sub(r"\s+(please|for\s+me|thanks|thank\s+you)\s*$", "", app).strip()
            app = app.strip("'\"")
            # Direct URL → open as URL via open_app path (dispatcher handles http)
            if app.startswith("http://") or app.startswith("https://"):
                return self._build_fast_graph("Open URL", "open_app", {"app_name": app})
            first = app.split()[0] if app else ""
            first_clean = re.sub(r"[^a-z0-9\-_+]", "", first)
            # Pronouns / deictics → let LLM or open_prior handle
            if not app or app in DEICTIC or first_clean in DEICTIC:
                return None
            # Multi-word non-apps ("these resources for me") → reject
            if len(app.split()) > 3:
                return None
            # Known apps only (conservative). Unknown single tokens still allowed
            # if short (e.g. "slack") — dispatcher resolves; multi-word unknown rejected.
            if app in KNOWN_APPS or first_clean in KNOWN_APPS:
                return self._build_fast_graph(
                    "Launch App", "open_app", {"app_name": first_clean if first_clean in KNOWN_APPS else app}
                )
            # Single short token unknown app — allow (brave, spotify variants)
            if len(app.split()) == 1 and 2 < len(first_clean) < 24:
                return self._build_fast_graph("Launch App", "open_app", {"app_name": first_clean})
            # Multi-word unknown ("these resources for me'") → DO NOT launch
            return None

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
        
        # ── 0. GRATITUDE & CONVERSATIONAL ACKNOWLEDGEMENT (PURE CHAT) ──
        # Gratitude messages like "thanks", "ok thanks", "thank you so much", "theek hai thanks"
        # MUST NEVER trigger physical OS actions, open/close apps, or modify workspace state.
        gratitude_exact = {
            "thanks", "thank you", "ok thanks", "okay thanks", "ok thank you", "okay thank you",
            "thanks a lot", "thank you so much", "thanks arova", "thank you arova",
            "great thanks", "got it thanks", "alright thanks", "perfect thanks",
            "cool thanks", "nice thanks", "awesome thanks", "sounds good", "looks good",
            "dhanyavad", "dhanyawad", "shukriya", "theek hai thanks", "accha thanks",
            "no thanks", "no thank you", "that's all", "thats all", "nothing else", "i'm good", "im good",
            "done thanks", "super thanks", "ok", "okay", "alright", "got it", "cool", "nice", "awesome",
            "theek hai", "accha", "sahi hai", "badhiya"
        }
        if norm in gratitude_exact or (
            any(norm.startswith(g) or norm.endswith(g) for g in ["thanks", "thank you", "dhanyavad", "shukriya"])
            and not any(act in norm for act in ["open ", "play ", "search ", "run ", "close ", "kill ", "set volume", "code ", "launch "])
        ):
            self._emit_state("CONVERSATIONAL_RESPONSE", "User expressed gratitude/acknowledgment.")
            return IntentClassification(
                category="chat",
                confidence=1.0,
                depth=ReasoningDepth.FAST,
                reasoning="User expressed gratitude or conversational acknowledgment."
            )

        # Check message history for screen analysis follow-up context (e.g. user says "yes" or "take a screenshot")
        prev_asst_msgs = [m["content"].lower() for m in reversed(messages[:-1]) if m["role"] == "assistant"]
        if prev_asst_msgs:
            last_asst = prev_asst_msgs[0]
            if any(w in last_asst for w in ["screenshot", "screen", "video", "check"]):
                if norm in ["yes", "yeah", "yep", "sure", "do it", "go ahead", "take screenshot", "take a screenshot", "take ss", "check it", "please do"]:
                    query = "Analyze the video and content on the screen to answer the user's question."
                    return IntentClassification(
                        category="fast_action",
                        confidence=1.0,
                        depth=ReasoningDepth.FAST,
                        fast_path_graph=self._build_fast_graph("Analyze Screen", "analyze_screen", {"query": query}),
                        reasoning="Follow-up affirmation for screen analysis."
                    )

        # 1. Attempt Fast Path (Zero-Shot Deterministic Bypass)
        fast_graph = self._get_fast_path(text, messages=messages)
        if fast_graph:
            self._emit_state("EXECUTING_FAST_PATH", f"Matched route: {fast_graph.name}")
            # Special category for opening links from prior assistant turn
            if getattr(fast_graph, "name", "") == "Open Prior Resources":
                return IntentClassification(
                    category="open_prior_resources",
                    confidence=1.0,
                    depth=ReasoningDepth.FAST,
                    fast_path_graph=None,
                    reasoning="User asked to open previously mentioned resources/links.",
                    action_hint="open_prior_resources",
                )
            return IntentClassification(
                category="fast_action",
                confidence=1.0,
                depth=ReasoningDepth.FAST,
                fast_path_graph=fast_graph,
                reasoning="Matched fast-path heuristic.",
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
            "- chat: The user is asking a QUESTION, requesting ADVICE, expressing GRATITUDE (e.g. 'thanks', 'ok thanks', 'thank you', 'dhanyavad'), or having a CONVERSATION.\n"
            "  Examples of 'chat': 'thanks', 'ok thanks', 'thank you so much', 'got it', 'cool', 'sounds good',\n"
            "  'recommend some YouTubers', 'what are good resources to learn Python', 'explain how Y works',\n"
            "  'hello', 'what can you do', any knowledge/advice/recommendation question.\n"
            "  CRITICAL RULE 1: If the user says 'thanks', 'ok thanks', 'thank you', 'got it', 'nice', or expresses gratitude/acknowledgment,\n"
            "  that is 100% 'chat' NOT 'action'. NEVER trigger an action or close/open apps when the user is simply thanking you.\n"
            "  CRITICAL RULE 2: If the user asks for advice or recommendations ('tell me good resources'), that is 'chat' NOT 'action'.\n"
            "- deep_planning: Requires multi-step execution, heavy memory recall, or complex orchestration.\n"
            "Return JSON matching: {\"category\": \"...\", \"confidence\": 0.0-1.0, \"reasoning\": \"...\"}"
        )
        
        budget = ReasoningBudget(max_tokens=200)
        route_messages = messages[-2:] if len(messages) > 2 else messages
        res = await self.models.invoke_structured(
            messages=route_messages, 
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
