import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from arova.core.ambience.schema import AmbientContext
from arova.core.cognition.memory_retrieval import RetrievedMemory

@dataclass
class CognitiveContext:
    """The unified intelligence substrate handed to the LLM."""
    ambient: AmbientContext
    memories: List[RetrievedMemory]
    policies: List[str]
    fragments: List[Any] = field(default_factory=list)
    presence_profile: Optional[Any] = None
    attention_narrative: Optional[str] = None
    active_workspace: Optional[Any] = None
    
    def to_system_prompt_block(self) -> str:
        """Formats the context layers into a strict instructional block."""
        lines = ["--- COGNITIVE CONTEXT ---"]
        
        if self.active_workspace and hasattr(self.active_workspace, 'get_six_questions'):
            lines.append("[ACTIVE COGNITIVE WORKSPACE]")
            q = self.active_workspace.get_six_questions()
            lines.append(f"Workspace: {q['what_am_i_doing']}")
            lines.append(f"Goal: {q['why_am_i_doing_it']}")
            lines.append(f"Progress & Health: {q['how_far_am_i']}")
            lines.append(f"Current Blocker: {q['whats_blocking_me']}")
            lines.append(f"Next Best Action: {q['what_should_i_do_next']}")
            lines.append(f"Reasoning: {q['why_do_you_believe_that']}\n")
        
        # 1. Ambient & Trajectory Narrative Layer
        lines.append("[ENVIRONMENT & ATTENTION]")
        if self.attention_narrative:
            lines.append(f"Narrative: {self.attention_narrative}")
        else:
            lines.append(f"Time of Day: {self.ambient.time_of_day}")
            lines.append(f"Active App: {self.ambient.active_app or 'None'}")
            lines.append(f"System Idle: {self.ambient.is_idle}")
            
        if self.ambient.open_windows:
            lines.append(f"Open Windows/Apps: {', '.join(self.ambient.open_windows)}")
        if self.ambient.playing_media:
            lines.append(f"Currently Playing Media: {', '.join(self.ambient.playing_media)}")
        
        # 2. Behavioral Modulation
        if self.presence_profile:
            lines.append("\n[BEHAVIORAL MODULATION]")
            lines.append(f"Verbosity: {self.presence_profile.verbosity}")
            lines.append(f"Cadence: {self.presence_profile.cadence}")
            lines.append(f"Emotional Tone: {self.presence_profile.emotional_temperature}")
            
        # 3. Context Provider Fragments
        if self.fragments:
            lines.append("\n[CONTEXT FRAGMENTS]")
            for f in self.fragments:
                lines.append(f"- [{f.provider_id}] {f.activity_summary} (Source: {f.source_identity})")
                
        # 4. Memory Layer
        if self.memories:
            lines.append("\n[MEMORY LAYER]")
            for m in self.memories:
                lines.append(f"- {m.entry.content} (Confidence: {m.relevance_score:.2f})")
                
        # 4. Policy Layer
        if self.policies:
            lines.append("\n[POLICY LAYER]")
            for p in self.policies:
                lines.append(f"! {p}")
                
        lines.append("-------------------------")
        return "\n".join(lines)

class ContextSynthesizer:
    """
    Fuses environmental, temporal, memory, and governance state 
    into a single snapshot before reasoning.
    """
    def __init__(self, provider_manager, memory_retrieval, ambient_observer, policy_runtime, environment_graph=None,
                 presence_modulator=None, narrative_generator=None, workspace_manager=None):
        self.provider_manager = provider_manager
        self.memory = memory_retrieval
        self.ambient = ambient_observer
        self.policy = policy_runtime
        self.environment_graph = environment_graph
        self.presence_modulator = presence_modulator
        self.narrative_generator = narrative_generator
        self.workspace_manager = workspace_manager
        
    async def synthesize(self, query: str) -> CognitiveContext:
        # Pull ambient state (legacy, soon to be fully replaced by fragments)
        amb_ctx = self.ambient.current_context or AmbientContext()
        
        # Poll all Context Providers
        fragments = await self.provider_manager.poll()
        
        # Pull heuristic memories
        mems = await self.memory.retrieve_for_context(query)
        
        # Pull active policies
        policies = [
            "DANGEROUS capabilities require explicit user approval via PolicyRuntime.",
            "Do not execute loops or recursive plans.",
            "Before launching an app or playing media, check the Open Windows and Playing Media lists in the Environment section to avoid repeating duplicate actions."
        ]
        
        # Synthesize Attention Narrative and Modulation Profile
        attention_narrative = None
        presence_profile = None
        
        if self.narrative_generator:
            traj = self.narrative_generator.get_current_trajectory()
            if traj and traj.narrative != "The user is currently idle.":
                # Provenance inclusion (e.g. "recovering focus [0.71 confidence] Derived from: deep_work_rising")
                attention_narrative = f"{traj.narrative} (Confidence: {traj.confidence:.2f}, Derived from: {', '.join(traj.derived_from)})"
                
                # Fetch modulation profile based on this trajectory
                if self.presence_modulator and self.environment_graph:
                    snap = self.environment_graph.snapshot()
                    derived = snap.get("_derived", {})
                    presence_profile = self.presence_modulator.modulate(traj, derived)
        
        active_ws = self.workspace_manager.get_active_workspace() if self.workspace_manager else None
        
        return CognitiveContext(
            ambient=amb_ctx,
            memories=mems,
            policies=policies,
            fragments=fragments,
            attention_narrative=attention_narrative,
            presence_profile=presence_profile,
            active_workspace=active_ws
        )
