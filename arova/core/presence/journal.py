import json
import os
import time
from dataclasses import dataclass, asdict
from typing import List

@dataclass
class PresenceReflection:
    timestamp: float
    context: str
    user_state: str
    action_taken: str
    interruption_level: float
    perceived_usefulness: float  # -1.0 to 1.0
    annoyance_score: float       # 0.0 to 1.0
    emotional_weight: float      # 0.0 to 1.0

class PresenceJournalSystem:
    """
    Local-First Reflection Architecture.
    Stores subjective telemetry securely without cloud sync.
    Implements Reflection Expiration (emotional decay).
    """
    def __init__(self, journal_dir: str = "~/.local/share/arova/journals/", retention_days: int = 7):
        self.journal_dir = os.path.expanduser(journal_dir)
        self.retention_seconds = retention_days * 86400
        
        if not os.path.exists(self.journal_dir):
            os.makedirs(self.journal_dir)
            
        self.journal_path = os.path.join(self.journal_dir, "presence_telemetry.jsonl")
        
    def record_reflection(self, reflection: PresenceReflection):
        """Append a subjective emotional record to the local JSONL log."""
        with open(self.journal_path, "a") as f:
            f.write(json.dumps(asdict(reflection)) + "\n")
            
    def read_valid_reflections(self) -> List[PresenceReflection]:
        """
        Reads reflections while implicitly ignoring expired ones.
        (Does not mutate the file immediately, just filters memory representation).
        """
        valid_reflections = []
        if not os.path.exists(self.journal_path):
            return valid_reflections
            
        current_time = time.time()
        with open(self.journal_path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                
                # Check Expiration (Emotional Decay)
                if current_time - data["timestamp"] <= self.retention_seconds:
                    valid_reflections.append(PresenceReflection(**data))
                    
        return valid_reflections
        
    def compact_journal(self):
        """
        Permanently purges expired emotional telemetry from disk to prevent
        long-term bias and preserve storage/privacy.
        """
        if not os.path.exists(self.journal_path):
            return
            
        valid = self.read_valid_reflections()
        
        # Rewrite file with only unexpired data
        with open(self.journal_path, "w") as f:
            for ref in valid:
                f.write(json.dumps(asdict(ref)) + "\n")
