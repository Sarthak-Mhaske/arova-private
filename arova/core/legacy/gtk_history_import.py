import json
import logging
from pathlib import Path
from typing import Optional
from arova.core.persistence.store import RuntimeStore
from arova.core.persistence.schema import RuntimeSnapshot

logger = logging.getLogger(__name__)

class LegacyGTKImporter:
    """
    Optional utility to migrate old flat JSON history into the 
    new Schema v4 RuntimeStore. This is never called automatically.
    """
    def __init__(self, history_path: str = "~/.cache/arova/history.json"):
        self.history_path = Path(history_path).expanduser()
        
    def import_legacy_history(self, store: RuntimeStore) -> bool:
        if not self.history_path.exists():
            logger.warning(f"No legacy history found at {self.history_path}")
            return False
            
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            messages = data.get("messages", [])
            if not messages:
                return False
                
            snapshot = store.hydrate()
            
            # Append legacy messages to the cold archive state (not hot)
            snapshot.cold_state.archived_sessions.append({
                "source": "legacy_gtk_import",
                "messages": messages
            })
            
            store.save(snapshot)
            logger.info(f"Successfully migrated {len(messages)} legacy messages to cold archive.")
            return True
            
        except Exception as e:
            logger.error(f"Failed to import legacy history: {e}")
            return False
