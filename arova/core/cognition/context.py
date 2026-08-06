import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from arova.core.ambience.schema import AmbientContext
from arova.core.cognition.memory_retrieval import RetrievedMemory

logger = logging.getLogger(__name__)

@dataclass
class CognitiveContext:
    """The unified intelligence substrate handed to the LLM — grounded in deterministic reality."""
    ambient: AmbientContext
    memories: List[RetrievedMemory]
    policies: List[str]
    fragments: List[Any] = field(default_factory=list)
    presence_profile: Optional[Any] = None
    attention_narrative: Optional[str] = None
    active_workspace: Optional[Any] = None
    # === TIER 1.1: Grounded deterministic state — never hallucinate ===
    grounded_resources: Optional[str] = None  # verbatim RealityLayer.resources
    recent_timeline: Optional[List[Dict[str, Any]]] = None  # last 15 timeline events
    momentum_capsule: Optional[Any] = None  # latest MomentumCapsule
    humility_note: Optional[str] = None  # low-confidence hedge instruction
    # === TIER 1.3: @-mentioned resources — verbatim file content ===
    mentioned_resources: Optional[str] = None  # verbatim file excerpts for @mention
    # === TIER 1 Search Unification: Unified search results — verbatim ===
    search_results: Optional[str] = None  # verbatim search index hits
    
    def to_system_prompt_block(self) -> str:
        """Formats the context layers into a strict instructional block — grounded first."""
        lines = ["--- COGNITIVE CONTEXT (GROUNDED) ---"]
        lines.append("You are Arova, a working-memory OS. You have VERBATIM deterministic state. NEVER hallucinate files, terminals, or decisions.")
        
        # 0. GROUND TRUTH — VERBATIM (MOST IMPORTANT — never hallucinate)
        if self.grounded_resources:
            lines.append("\n[GROUND TRUTH — VERBATIM DETERMINISTIC STATE — NEVER HALLUCINATE]")
            lines.append("These are EXACT files, terminals, repos, and browser resources observed via OS telemetry in the last session. Cite them verbatim.")
            lines.append(self.grounded_resources)
        else:
            lines.append("\n[GROUND TRUTH]")
            lines.append("No verbatim workspace resources observed yet (fresh boot). Do not invent files.")

        # 0a. @-MENTIONED RESOURCES — verbatim file excerpts (HIGHEST PRIORITY)
        if self.mentioned_resources:
            lines.append("\n[MENTIONED RESOURCES — VERBATIM FILE EXCERPTS — USER EXPLICITLY @-TAGGED]")
            lines.append("User explicitly @-mentioned these files. Treat as ground truth, higher priority than general history.")
            lines.append(self.mentioned_resources)

        # 0a2. SEARCH RESULTS — verbatim unified index hits (for 'find ...' queries)
        if self.search_results:
            lines.append("\n[SEARCH RESULTS — VERBATIM UNIFIED INDEX — DO NOT HALLUCINATE]")
            lines.append("These are exact hits from the local unified search index (files, decisions, docs). Cite them verbatim, don't invent.")
            lines.append(self.search_results)

        # 0b. Timeline — recent lived experience
        if self.recent_timeline:
            lines.append("\n[RECENT TIMELINE — LAST EVENTS (trajectory)]")
            for ev in self.recent_timeline[-15:]:
                cat = ev.get('category', 'unknown')
                title = ev.get('title', '')[:120]
                desc = ev.get('description', '')[:180]
                ts = ev.get('timestamp', 0)
                lines.append(f"- [{cat}] {title}: {desc}")
        # 0c. Momentum capsule — continuity
        if self.momentum_capsule:
            try:
                lines.append("\n[CONTINUITY CAPSULE — MOMENTUM]")
                # Support both dict (from JSON) and object
                if isinstance(self.momentum_capsule, dict):
                    room = self.momentum_capsule.get('room', 'unknown')
                    obj = self.momentum_capsule.get('objective', '')
                    prog = self.momentum_capsule.get('progress', '')
                    blockers = ", ".join(self.momentum_capsule.get('blockers', []))
                    nxt = self.momentum_capsule.get('next_action', '')
                    avoid = ", ".join(self.momentum_capsule.get('avoid_list', []))
                else:
                    room = getattr(self.momentum_capsule, 'room', 'unknown')
                    obj = getattr(self.momentum_capsule, 'objective', '')
                    prog = getattr(self.momentum_capsule, 'progress', '')
                    blockers = ", ".join(getattr(self.momentum_capsule, 'blockers', []) or [])
                    nxt = getattr(self.momentum_capsule, 'next_action', '')
                    avoid = ", ".join(getattr(self.momentum_capsule, 'avoid_list', []) or [])
                lines.append(f"Room: {room} | Objective: {obj}")
                if prog: lines.append(f"Progress: {prog}")
                if blockers: lines.append(f"Blockers: {blockers}")
                if nxt: lines.append(f"Next Action: {nxt} (do this first on resume)")
                if avoid: lines.append(f"Avoid/Dead ends: {avoid} (do NOT retry)")
            except Exception as e:
                logger.debug(f"Failed to render capsule: {e}")

        if self.humility_note:
            lines.append(f"\n[HUMILITY INSTRUCTION]\n{self.humility_note}")

        if self.active_workspace and hasattr(self.active_workspace, 'get_seven_questions'):
            lines.append("\n[ACTIVE COGNITIVE WORKSPACE — SYNTHESIZED]")
            q = self.active_workspace.get_seven_questions()
            # Use seven questions verbatim — they already hedge if confidence <85%
            lines.append(f"Workspace: {q['what_am_i_doing']}")
            lines.append(f"Goal: {q['why_am_i_doing_it']}")
            lines.append(f"Progress & Health: {q['how_far_am_i']}")
            lines.append(f"Current Blocker: {q['whats_blocking_me']}")
            lines.append(f"Next Best Action: {q['what_should_i_do_next']}")
            lines.append(f"Reasoning: {q['why_do_you_believe_that']}")
            # Also surface what_changed verbatim
            if 'what_changed' in q:
                lines.append(f"What Changed: {q['what_changed']}")

        # 1. Ambient & Trajectory Narrative Layer (only if presence enabled)
        lines.append("\n[ENVIRONMENT & ATTENTION]")
        if self.attention_narrative:
            lines.append(f"Narrative: {self.attention_narrative}")
        else:
            try:
                lines.append(f"Time of Day: {self.ambient.time_of_day}")
                lines.append(f"Active App: {self.ambient.active_app or 'None'}")
                lines.append(f"System Idle: {self.ambient.is_idle}")
                if getattr(self.ambient, "open_windows", None):
                    lines.append(f"Open Windows/Apps: {', '.join(self.ambient.open_windows)}")
                if getattr(self.ambient, "playing_media", None):
                    lines.append(f"Currently Playing Media: {', '.join(self.ambient.playing_media)}")
            except Exception:
                lines.append("Ambient: minimal mode (no live observer)")

        # 2. Behavioral Modulation — only if present
        if self.presence_profile:
            lines.append("\n[BEHAVIORAL MODULATION]")
            lines.append(f"Verbosity: {self.presence_profile.verbosity}")
            lines.append(f"Cadence: {self.presence_profile.cadence}")
            lines.append(f"Emotional Tone: {self.presence_profile.emotional_temperature}")
            
        # 3. Context Provider Fragments (OS telemetry)
        if self.fragments:
            lines.append("\n[CONTEXT FRAGMENTS — OS TELEMETRY]")
            for f in self.fragments:
                try:
                    lines.append(f"- [{f.provider_id}] {f.activity_summary} (Source: {f.source_identity})")
                except:
                    lines.append(f"- {str(f)[:200]}")
                
        # 4. Memory Layer (personalization moat)
        if self.memories:
            lines.append("\n[MEMORY LAYER — PERSONALIZATION]")
            for m in self.memories:
                try:
                    lines.append(f"- {m.entry.content} (Relevance: {m.relevance_score:.2f}, Why: {m.why_retrieved})")
                except:
                    lines.append(f"- {str(m)[:200]}")
                
        # 5. Policy Layer
        if self.policies:
            lines.append("\n[POLICY LAYER]")
            for p in self.policies:
                lines.append(f"! {p}")
                
        lines.append("\n--- END GROUNDED CONTEXT ---")
        lines.append("Instruction: When user asks 'where was I?' or 'fix the bug', ALWAYS prioritize GROUND TRUTH and TIMELINE over generic knowledge. Cite exact files/terminals. If confidence is low, hedge with 'I think...' and ask for confirmation.")
        return "\n".join(lines)

class ContextSynthesizer:
    """
    Fuses environmental, temporal, memory, and governance state 
    into a single snapshot before reasoning — now with VERBATIM deterministic grounding.
    """
    def __init__(self, provider_manager, memory_retrieval, ambient_observer, policy_runtime, environment_graph=None,
                 presence_modulator=None, narrative_generator=None, workspace_manager=None,
                 timeline_store=None, capsule_generator=None, search_index=None):
        self.provider_manager = provider_manager
        self.memory = memory_retrieval
        self.ambient = ambient_observer
        self.policy = policy_runtime
        self.environment_graph = environment_graph
        self.presence_modulator = presence_modulator
        self.narrative_generator = narrative_generator
        self.workspace_manager = workspace_manager
        self.timeline_store = timeline_store
        self.capsule_generator = capsule_generator
        self.search_index = search_index
        
    async def synthesize(self, query: str, mentions: Optional[List[str]] = None) -> CognitiveContext:
        # === Ambient — handle minimal mode where observer is None ===
        if self.ambient and hasattr(self.ambient, 'current_context') and self.ambient.current_context:
            amb_ctx = self.ambient.current_context
        else:
            amb_ctx = AmbientContext()

        # Poll all Context Providers — handle provider_manager None gracefully
        fragments = []
        try:
            if self.provider_manager:
                fragments = await self.provider_manager.poll()
        except Exception as e:
            logger.debug(f"Provider poll failed (minimal mode ok): {e}")
        
        # Pull memories — hybrid vector + heuristic (personalization moat)
        mems = []
        try:
            mems = await self.memory.retrieve_for_context(query)
        except Exception as e:
            logger.debug(f"Memory retrieval failed: {e}")

        # === Search Unification: Unified index hits for chat (so 'find X' doesn't hallucinate) ===
        search_results_str = None
        if self.search_index and query and len(query.strip()) > 2:
            try:
                q_lower = query.lower()
                is_search_like = any(w in q_lower for w in ["find", "search", "lookup", "where is", "where's", "show me", "docs", "documentation", "file", "decision", "open", "locate", "how to"])
                is_long_query = len(q_lower.split()) >= 3 and not any(g in q_lower for g in ["hello", "hi ", "hey ", "thanks", "thank you", "where was i", "what was i"])
                if is_search_like or is_long_query:
                    # Ensure active workspace indexed for fresh hits
                    if self.workspace_manager and self.workspace_manager.get_active_workspace():
                        try:
                            self.search_index.index_workspace(self.workspace_manager.get_active_workspace())
                        except:
                            pass
                    hits = self.search_index.search(query, limit=3)
                    if hits:
                        lines = []
                        for h in hits:
                            # Use payload for file path if available
                            loc = h.payload.get("resource_path") or h.payload.get("url") or h.payload.get("workspace_id") or ""
                            loc_str = f" -> {loc}" if loc else ""
                            lines.append(f"- [{h.kind}] {h.title}: {h.summary[:140]}{loc_str}")
                        search_results_str = "\n".join(lines)
                        logger.debug(f"Search unification: {len(hits)} hits for '{query[:30]}'")
            except Exception as e:
                logger.debug(f"Search unification failed: {e}")
        
        # Pull active policies
        policies = [
            "DANGEROUS capabilities require explicit user approval via PolicyRuntime.",
            "Do not execute loops or recursive plans.",
            "Before launching an app or playing media, check the Open Windows and Playing Media lists in the Environment section to avoid repeating duplicate actions.",
            "NEVER hallucinate file paths, terminal CWDs, or decisions — only cite GROUND TRUTH.",
            "If SEARCH RESULTS are present, cite them verbatim for 'find/search' queries — do not invent docs."
        ]
        
        # === Presence-gated synthesis — skip if disabled ===
        attention_narrative = None
        presence_profile = None
        
        if self.narrative_generator and self.presence_modulator and self.environment_graph:
            try:
                traj = self.narrative_generator.get_current_trajectory()
                if traj and traj.narrative != "The user is currently idle.":
                    attention_narrative = f"{traj.narrative} (Confidence: {traj.confidence:.2f}, Derived from: {', '.join(traj.derived_from)})"
                    snap = self.environment_graph.snapshot()
                    derived = snap.get("_derived", {})
                    presence_profile = self.presence_modulator.modulate(traj, derived)
            except Exception as e:
                logger.debug(f"Presence synthesis skipped (minimal mode): {e}")
        
        active_ws = self.workspace_manager.get_active_workspace() if self.workspace_manager else None

        # === TIER 1.1: Grounded deterministic extraction ===
        grounded_resources_str = None
        recent_timeline = None
        momentum_capsule = None
        humility_note = None

        # === TIER 1.3: Resolve @-mentions to verbatim file excerpts ===
        mentioned_resources_str = None
        if mentions and active_ws:
            try:
                import os
                excerpts = []
                # Build lookup: basename -> full path from reality
                basename_to_paths = {}
                if hasattr(active_ws, 'reality') and active_ws.reality.resources:
                    for rid, r in active_ws.reality.resources.items():
                        ident = r.get('identity', rid) if isinstance(r, dict) else str(rid)
                        if ident and "/" in ident:
                            basename_to_paths[os.path.basename(ident)] = ident
                            basename_to_paths[ident] = ident
                seen_paths = set()
                for mention in mentions[:5]:  # cap 5 mentions
                    m = mention.strip().lstrip('@').strip()  # normalize @runtime.py -> runtime.py
                    if not m:
                        continue
                    # Resolve to full path
                    full_path = basename_to_paths.get(m) or basename_to_paths.get(os.path.basename(m)) or m
                    # Deduplicate by full_path
                    if full_path in seen_paths:
                        continue
                    seen_paths.add(full_path)
                    if not os.path.isabs(full_path):
                        # Try to resolve via repo_paths
                        if hasattr(active_ws, 'interpretation') and active_ws.interpretation.repo_paths:
                            for rp in active_ws.interpretation.repo_paths:
                                cand = os.path.join(rp, m)
                                if os.path.exists(cand):
                                    full_path = cand
                                    break
                    # Also try as-is if exists
                    if os.path.exists(full_path) and os.path.isfile(full_path):
                        try:
                            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read(4000)  # first 4k chars
                            lines = content.split('\n')[:80]
                            numbered = "\n".join(f"{i+1:3d} | {line}" for i, line in enumerate(lines))
                            excerpts.append(f"--- FILE: {full_path} ---\n{numbered}\n--- END FILE ---")
                        except Exception as e:
                            excerpts.append(f"--- FILE: {full_path} (read failed: {e}) ---")
                    else:
                        # If not found on FS, still note the mention as grounded intent
                        excerpts.append(f"--- MENTIONED: {m} (resolved to {full_path}) — file not found on disk, but user explicitly referenced it. Treat as context. ---")
                if excerpts:
                    mentioned_resources_str = "\n".join(excerpts)
            except Exception as e:
                logger.debug(f"Mention resolution failed: {e}")

        try:
            if active_ws:
                # A. Verbatim resources from RealityLayer
                if hasattr(active_ws, 'reality') and active_ws.reality.resources:
                    res_lines = []
                    # Sort by last_seen if available, else insertion order
                    resources_items = list(active_ws.reality.resources.items())
                    # Keep last 20 observed
                    for res_id, res in resources_items[-20:]:
                        identity = res.get('identity', res_id) if isinstance(res, dict) else str(res)
                        rtype = res.get('type', 'unknown') if isinstance(res, dict) else 'unknown'
                        summary = (res.get('summary', '')[:120] if isinstance(res, dict) else '') 
                        # Also capture line/col if file
                        line_info = ""
                        if isinstance(res, dict) and res.get('line'):
                            line_info = f":{res.get('line')}"
                            if res.get('col'): line_info += f":{res.get('col')}"
                        res_lines.append(f"- [{rtype}] {identity}{line_info} {summary}".strip())
                    if res_lines:
                        grounded_resources_str = "\n".join(res_lines)
                        # Add repo paths
                        if hasattr(active_ws, 'interpretation') and active_ws.interpretation.repo_paths:
                            grounded_resources_str += f"\nRepositories: {', '.join(active_ws.interpretation.repo_paths[:3])}"
                        # Add browser domains if any
                        if hasattr(active_ws, 'interpretation') and active_ws.interpretation.browser_domains:
                            grounded_resources_str += f"\nBrowserDomains: {', '.join(active_ws.interpretation.browser_domains[:5])}"

                # B. Humility note if confidence low
                if hasattr(active_ws, 'understanding') and hasattr(active_ws.understanding, 'confidence'):
                    conf_score = getattr(active_ws.understanding.confidence, 'score', 0)
                    if 0 < conf_score < 70:
                        humility_note = f"Overall confidence is {conf_score}% (LOW). You MUST hedge: start with 'I think...' and offer to confirm. Never state uncertain blockers as fact."
                    elif conf_score == 0:
                        humility_note = "No confidence yet (fresh workspace). Ask clarifying questions rather than assuming goal."

                # C. Recent timeline — try timeline_store, else fallback to workspace timeline_event_ids
                if self.timeline_store and hasattr(self.timeline_store, 'events'):
                    # Sync read from hot storage (events is list)
                    try:
                        # events are TimelineEvent objects, convert to dict
                        from dataclasses import asdict
                        recent_timeline = []
                        for ev in self.timeline_store.events[:15]:
                            try:
                                recent_timeline.append(asdict(ev))
                            except:
                                recent_timeline.append({"title": str(ev), "category": "unknown", "description": ""})
                    except Exception as e:
                        logger.debug(f"Timeline read failed: {e}")
                # Fallback: if no timeline_store but workspace has events, note it
                elif hasattr(active_ws.reality, 'timeline_event_ids') and active_ws.reality.timeline_event_ids:
                    recent_timeline = [{"category": "workspace", "title": tid, "description": "linked event"} for tid in active_ws.reality.timeline_event_ids[-10:]]

                # D. Momentum capsule — latest from store or generator
                if self.timeline_store:
                    try:
                        # Try file-backed capsules (sync read)
                        cap = self.timeline_store.get_latest_unresumed_capsule()
                        if cap:
                            momentum_capsule = cap
                    except Exception as e:
                        logger.debug(f"Capsule read failed: {e}")
        except Exception as e:
            logger.debug(f"Grounded synthesis failed (non-fatal): {e}")

        return CognitiveContext(
            ambient=amb_ctx,
            memories=mems,
            policies=policies,
            fragments=fragments,
            attention_narrative=attention_narrative,
            presence_profile=presence_profile,
            active_workspace=active_ws,
            grounded_resources=grounded_resources_str,
            recent_timeline=recent_timeline,
            momentum_capsule=momentum_capsule,
            humility_note=humility_note,
            mentioned_resources=mentioned_resources_str,
            search_results=search_results_str
        )
