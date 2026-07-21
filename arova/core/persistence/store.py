import os
import time
import json
import glob
import logging
from typing import Optional
from pathlib import Path
from arova.core.persistence.schema import RuntimeSnapshot, RUNTIME_SCHEMA_VERSION

logger = logging.getLogger(__name__)

class RuntimeStore:
    """
    Manages generation-based transactional persistence of the cognitive substrate.
    """
    def __init__(self, storage_dir: str = "~/.arova/runtime"):
        self.storage_dir = Path(os.path.expanduser(storage_dir))
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.current_snapshot: Optional[RuntimeSnapshot] = None
        
    def hydrate(self) -> RuntimeSnapshot:
        """Loads the most recent valid generation of the snapshot."""
        # Find all v4 generations
        files = glob.glob(str(self.storage_dir / "runtime_v4_*.json"))
        files.sort(reverse=True) # newest first
        
        # Also check current.json
        current_file = self.storage_dir / "current.json"
        
        candidates = []
        if current_file.exists():
            candidates.append(current_file)
        candidates.extend([Path(f) for f in files])
        
        for candidate in candidates:
            try:
                with open(candidate, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                if data.get("schema_version") == RUNTIME_SCHEMA_VERSION:
                    logger.info(f"Hydrated RuntimeSnapshot from {candidate.name}")
                    self.current_snapshot = RuntimeSnapshot.from_dict(data)
                    return self.current_snapshot
            except Exception as e:
                logger.warning(f"Failed to load snapshot {candidate}: {e}")
                
        # If no valid snapshot exists, create a fresh one
        logger.info("No valid v4 snapshot found. Generating fresh RuntimeSnapshot.")
        self.current_snapshot = RuntimeSnapshot()
        return self.current_snapshot

    def save(self, snapshot: RuntimeSnapshot):
        """Saves the snapshot transactionally with generational rotation."""
        if isinstance(snapshot, dict):
            try:
                self.current_snapshot = RuntimeSnapshot.from_dict(snapshot)
            except Exception:
                self.current_snapshot = snapshot
            ts = snapshot.get("timestamp", time.time())
            data = snapshot
        elif hasattr(snapshot, "to_dict"):
            self.current_snapshot = snapshot
            ts = getattr(snapshot, "timestamp", time.time())
            data = snapshot.to_dict()
        else:
            self.current_snapshot = snapshot
            ts = getattr(snapshot, "timestamp", time.time())
            from dataclasses import asdict
            data = asdict(snapshot)
            
        # Generation sequence
        timestamp_ms = int(ts * 1000)
        gen_filename = f"runtime_v4_{timestamp_ms}.json"
        gen_path = self.storage_dir / gen_filename
        
        tmp_path = self.storage_dir / "current.json.tmp"
        current_path = self.storage_dir / "current.json"
        
        try:
            # 1. Write to specific generation
            with open(gen_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
            # 2. Write to temp current
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
            # 3. Atomic swap
            os.replace(tmp_path, current_path)
            
            # 4. Clean up old generations (keep last 5)
            self._cleanup_old_generations()
        except Exception as e:
            logger.error(f"Critical failure saving RuntimeSnapshot: {e}")
            if tmp_path.exists():
                tmp_path.unlink()

    def _cleanup_old_generations(self):
        files = glob.glob(str(self.storage_dir / "runtime_v4_*.json"))
        files.sort(reverse=True)
        # Keep the latest 5
        for old_file in files[5:]:
            try:
                os.remove(old_file)
            except OSError as e:
                logger.debug(f"Could not remove old generation file {old_file}: {e}")
