"""
ApplicationAffinity — learns which applications the user actually uses.

Instead of relying on MIME defaults, Arova observes which application the
user opens files with and builds a preference model from real usage.

Fed from capture.EVENT_INGESTED events.  Persisted in workspace state.
"""
import time
import logging
from collections import defaultdict
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ApplicationAffinity:
    """
    Tracks per-extension application usage and produces a ranked preference.

    Example internal state after real usage::

        {
            ".py": {"code": 47, "cursor": 2, "nvim": 1},
            ".md": {"obsidian": 12, "code": 3},
            ".blend": {"blender": 8},
        }

    ``get_preferred_app(".py")`` returns ``"code"`` (highest count).
    """

    def __init__(self):
        # extension -> {exec_name -> usage_count}
        self._usage: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._last_updated: float = 0.0

    def record_usage(self, file_extension: str, application_id_or_exec: str) -> None:
        """
        Record that a resource with the given extension/kind was opened in an application.
        Can record against either executable names or canonical application identities
        (e.g., 'com.microsoft.vscode', 'cursor.desktop').
        """
        if not file_extension or not application_id_or_exec:
            return
        ext = file_extension.lower() if file_extension.startswith(".") else f".{file_extension.lower()}"
        app_key = application_id_or_exec.strip().lower()
        self._usage[ext][app_key] += 1
        self._last_updated = time.time()

    def record_outcome(self, file_extension: str, application_id_or_exec: str, positive: bool = True, weight: int = 1) -> None:
        """
        Record the actual usage outcome of an executed launch (Affinity feedback loop).
        If positive (succeeded, focused, or actually used), increases affinity (+weight).
        If negative (immediately closed or failed), decreases affinity (-weight).
        """
        if not file_extension or not application_id_or_exec:
            return
        ext = file_extension.lower() if file_extension.startswith(".") else f".{file_extension.lower()}"
        app_key = application_id_or_exec.strip().lower()
        if positive:
            self._usage[ext][app_key] += weight
        else:
            current = self._usage[ext][app_key]
            self._usage[ext][app_key] = max(0, current - weight)
        self._last_updated = time.time()

    def get_preferred_app(self, file_extension: str) -> Optional[str]:
        """
        Return the executable name the user most frequently uses for this extension.
        Returns None if no usage data exists.
        """
        ext = file_extension.lower() if file_extension.startswith(".") else f".{file_extension.lower()}"
        ext_data = self._usage.get(ext)
        if not ext_data:
            return None
        return max(ext_data, key=ext_data.get)

    def get_affinity_distribution(self, file_extension: str) -> Dict[str, float]:
        """
        Return a normalized probability distribution for the given extension.

        Example: {".py": {"code": 0.94, "cursor": 0.04, "nvim": 0.02}}
        """
        ext = file_extension.lower() if file_extension.startswith(".") else f".{file_extension.lower()}"
        ext_data = self._usage.get(ext)
        if not ext_data:
            return {}
        total = sum(ext_data.values())
        if total == 0:
            return {}
        return {k: round(v / total, 4) for k, v in sorted(ext_data.items(), key=lambda x: -x[1])}

    def get_all_affinities(self) -> Dict[str, Dict[str, float]]:
        """Return the full affinity map (all extensions)."""
        return {ext: self.get_affinity_distribution(ext) for ext in self._usage}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "usage": {ext: dict(apps) for ext, apps in self._usage.items()},
            "last_updated": self._last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApplicationAffinity":
        instance = cls()
        for ext, apps in data.get("usage", {}).items():
            for app_exec, count in apps.items():
                instance._usage[ext][app_exec] = int(count)
        instance._last_updated = data.get("last_updated", 0.0)
        return instance
