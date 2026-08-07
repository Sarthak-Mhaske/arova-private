import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

@dataclass
class SearchableItem:
    """
    Unified searchable object (`Phase 6 Rule 2`).
    Every cognitive object (`Decision`, `Question`, `Workspace`, `Conversation`, `BrowserTab`, `File`)
    exposes this exact schema so that the search engine queries across all kinds seamlessly.
    """
    id: str
    title: str
    summary: str
    keywords: List[str]
    timestamp: float
    kind: str  # 'Decision', 'Question', 'Workspace', 'Conversation', 'BrowserTab', 'File'
    workspace_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchableItem":
        return cls(**data)


class SearchIndex:
    """
    Single unified search index (`Phase 6`).
    Provides instantaneous retrieval across typical local workspaces by scoring matches
    on `title`, `summary`, and `keywords` weighted by temporal recency.
    """
    def __init__(self):
        self._items: Dict[str, SearchableItem] = {}
        # Initial additive weights (`Phase 7 Point 2`), dynamically tunable by telemetry
        try:
            from arova.core.config.loader import load_config
            cfg = load_config()
            self.weights = cfg.get("search_weights", {
                "text_match": 0.35,
                "recency": 0.20,
                "time_spent": 0.15,
                "revisit_count": 0.15,
                "decision_weight": 0.10,
                "pin": 0.05
            })
        except Exception:
            self.weights = {
                "text_match": 0.35,
                "recency": 0.20,
                "time_spent": 0.15,
                "revisit_count": 0.15,
                "decision_weight": 0.10,
                "pin": 0.05
            }
        
        self._last_workspace_idx_ts: Dict[str, float] = {}

    def calibrate_search_weights(self, telemetry_adjustments: Dict[str, float]) -> None:
        """Adjust search ranking weights empirically from click telemetry."""
        for k, v in telemetry_adjustments.items():
            if k in self.weights and isinstance(v, (int, float)):
                self.weights[k] = max(0.0, min(1.0, float(v)))
        # Normalize weights so they sum to 1.0
        total = sum(self.weights.values())
        if total > 0:
            for k in self.weights:
                self.weights[k] /= total
        logger.info(f"SearchIndex: Calibrated additive ranking weights -> {self.weights}")

    def index_workspace(self, workspace: Any) -> None:
        """Inject active workspace reality context into unified search index."""
        if not workspace or not hasattr(workspace, "reality") or not workspace.reality.resources:
            return
            
        last_synth = getattr(workspace, "last_synthesized_at", 0.0)
        cached_ts = self._last_workspace_idx_ts.get(workspace.workspace_id, -1)
        if last_synth > 0 and last_synth == cached_ts:
            return # Skip if already indexed for this synthesis turn
            
        self._last_workspace_idx_ts[workspace.workspace_id] = last_synth
        
        for k, v in workspace.reality.resources.items():
            self.index_item(v)

    def index_item(self, item: SearchableItem) -> None:
        """Add or update an item in the unified search index."""
        if not item or not item.id:
            return
        self._items[item.id] = item

    def remove_item(self, item_id: str) -> None:
        """Remove an item from the search index."""
        self._items.pop(item_id, None)

    def clear(self) -> None:
        """Clear all indexed items."""
        self._items.clear()

    def get_all_items(self) -> List[SearchableItem]:
        return list(self._items.values())

    def index_canonical_event(self, event: Any) -> Optional[SearchableItem]:
        """Convert and index a `CanonicalActivityEvent` or `TimelineEvent` automatically."""
        if not event:
            return None
        
        event_id = getattr(event, "event_id", getattr(event, "id", str(time.time())))
        payload = getattr(event, "normalized_payload", getattr(event, "metadata", {}))
        kind = payload.get("kind") or "File"
        title = payload.get("title") or getattr(event, "title", "Activity Item")
        summary = payload.get("summary") or getattr(event, "description", "")
        keywords = payload.get("keywords") or [w.lower() for w in f"{title} {summary}".split() if len(w) > 3]
        workspace_id = payload.get("workspace_id")
        ts = getattr(event, "timestamp", time.time())

        item = SearchableItem(
            id=event_id,
            title=str(title),
            summary=str(summary),
            keywords=list(set(keywords)),
            timestamp=ts,
            kind=kind,
            workspace_id=workspace_id,
            payload=payload if isinstance(payload, dict) else {"raw": str(payload)}
        )
        self.index_item(item)
        return item

    def index_workspace(self, workspace: Any) -> SearchableItem:
        """Index a CognitiveWorkspace object."""
        ws_id = getattr(workspace, "workspace_id", "")
        title = getattr(workspace, "title", "Workspace")
        summary = getattr(workspace, "understanding", getattr(workspace, "state_summary", ""))
        if hasattr(summary, "goal"):
            summary_str = f"{summary.goal} {summary.what_changed} {summary.trajectory_story}"
        else:
            summary_str = str(summary)

        keywords = [w.lower() for w in f"{title} {summary_str}".split() if len(w) > 3]
        item = SearchableItem(
            id=f"ws_{ws_id}",
            title=str(title),
            summary=str(summary_str),
            keywords=list(set(keywords)),
            timestamp=time.time(),
            kind="Workspace",
            workspace_id=ws_id,
            payload={"workspace_id": ws_id, "status": getattr(workspace.understanding.health, "status", "Exploring") if hasattr(workspace, "understanding") else "Exploring"}
        )
        self.index_item(item)
        
        # Also index any explicit decisions or questions stored in the workspace understanding
        if hasattr(workspace, "understanding") and workspace.understanding:
            for idx, dec in enumerate(getattr(workspace.understanding, "decisions", [])):
                dec_str = dec if isinstance(dec, str) else str(dec.get("text", dec) if isinstance(dec, dict) else dec)
                self.index_item(SearchableItem(
                    id=f"ws_{ws_id}_dec_{idx}",
                    title=f"Decision: {dec_str[:40]}...",
                    summary=dec_str,
                    keywords=[w.lower() for w in dec_str.split() if len(w) > 3],
                    timestamp=time.time(),
                    kind="Decision",
                    workspace_id=ws_id,
                    payload={"text": dec_str, "workspace_id": ws_id}
                ))
            for idx, q in enumerate(getattr(workspace.understanding, "open_questions", [])):
                q_str = q if isinstance(q, str) else str(q.get("text", q) if isinstance(q, dict) else q)
                self.index_item(SearchableItem(
                    id=f"ws_{ws_id}_q_{idx}",
                    title=f"Question: {q_str[:40]}...",
                    summary=q_str,
                    keywords=[w.lower() for w in q_str.split() if len(w) > 3],
                    timestamp=time.time(),
                    kind="Question",
                    workspace_id=ws_id,
                    payload={"text": q_str, "workspace_id": ws_id}
                ))
        return item

    def search(self, query: str, limit: int = 20, kind_filter: Optional[str] = None) -> List[SearchableItem]:
        """
        Instantaneous search across the unified index (`Phase 6 Rule 2`).
        Matches across `title`, `summary`, and `keywords`.
        Returns sorted by relevance and recency.
        """
        if not query or not query.strip():
            # If empty query, return most recent items
            items = list(self._items.values())
            if kind_filter:
                items = [it for it in items if it.kind.lower() == kind_filter.lower()]
            items.sort(key=lambda x: x.timestamp, reverse=True)
            return items[:limit]

        query_terms = [t.lower() for t in query.strip().split() if t]
        scored_results: List[tuple[float, SearchableItem]] = []

        now = time.time()
        for item in self._items.values():
            if kind_filter and item.kind.lower() != kind_filter.lower():
                continue

            title_lower = item.title.lower()
            summary_lower = item.summary.lower()
            keywords_lower = set(k.lower() for k in item.keywords)

            score = 0.0
            matched_terms = 0

            for term in query_terms:
                term_matched = False
                # Exact title match / substring
                if term in title_lower:
                    score += 10.0
                    if title_lower.startswith(term):
                        score += 5.0
                    term_matched = True
                # Summary match
                if term in summary_lower:
                    score += 4.0
                    term_matched = True
                # Keyword match
                if any(term in k or k in term for k in keywords_lower):
                    score += 6.0
                    term_matched = True

                if term_matched:
                    matched_terms += 1

            # Only include items that matched at least one query term
            if matched_terms > 0:
                # Multi-term boost: if all terms matched, give a big boost
                if matched_terms == len(query_terms):
                    score *= 2.0
                
                # Multi-Factor Additive Ranking Formula (`Phase 7 Point 2`)
                # Normalized factors (0-100) combined using telemetry-calibrated weights
                text_norm = min(100.0, score * 3.5)
                
                age_hours = max(0.0, (now - item.timestamp) / 3600.0)
                recency_norm = max(0.0, 100.0 * (1.0 - min(1.0, age_hours / 168.0))) # 100 today -> 0 at 7 days
                
                time_spent_sec = float(item.payload.get("time_spent_sec", item.payload.get("duration", 0.0)))
                time_spent_norm = min(100.0, (time_spent_sec / 7200.0) * 100.0) # 100 at 2+ hours
                
                return_count = int(item.payload.get("return_count", item.payload.get("visit_count", 1)))
                revisit_norm = min(100.0, max(0, return_count - 1) * 25.0) # 100 at 5+ visits
                
                decision_norm = 100.0 if item.kind.lower() == "decision" else min(100.0, float(item.payload.get("decision_weight", item.payload.get("importance", 0.0))) * 100.0)
                
                pin_norm = 100.0 if item.payload.get("pinned", False) or item.payload.get("is_pinned", False) else 0.0
                
                final_score = (
                    self.weights["text_match"] * text_norm +
                    self.weights["recency"] * recency_norm +
                    self.weights["time_spent"] * time_spent_norm +
                    self.weights["revisit_count"] * revisit_norm +
                    self.weights["decision_weight"] * decision_norm +
                    self.weights["pin"] * pin_norm
                )
                scored_results.append((final_score, item))

        scored_results.sort(key=lambda x: (x[0], x[1].timestamp), reverse=True)
        return [item for score, item in scored_results[:limit]]
