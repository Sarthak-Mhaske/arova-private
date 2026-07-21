import os
import threading
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

@dataclass
class ResourceItem:
    """
    Normalized Resource Item (`Phase 7`).
    Single canonical definition referenced by Resume, Search, Timeline, and Restore.
    """
    resource_id: str
    type: str                  # "file" | "url" | "terminal" | "repository"
    display_name: str
    exists: bool = True
    file: Optional[str] = None
    url: Optional[str] = None
    terminal: Optional[str] = None
    repository: Optional[str] = None
    launch_command: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "type": self.type,
            "display_name": self.display_name,
            "exists": self.exists,
            "file": self.file,
            "url": self.url,
            "terminal": self.terminal,
            "repository": self.repository,
            "launch_command": self.launch_command,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceItem":
        return cls(
            resource_id=data["resource_id"],
            type=data["type"],
            display_name=data.get("display_name", data["resource_id"]),
            exists=data.get("exists", True),
            file=data.get("file"),
            url=data.get("url"),
            terminal=data.get("terminal"),
            repository=data.get("repository"),
            launch_command=data.get("launch_command"),
            metadata=data.get("metadata", {})
        )

class ResourceRegistry:
    """
    Central Normalized Resource Registry (`Phase 7`).
    Normalizes file paths, browser URLs, terminal working directories, and repo paths
    so no subsystem remembers paths differently.
    """
    def __init__(self):
        self._resources: Dict[str, ResourceItem] = {}
        self._lock = threading.RLock()

    def normalize_resource_id(self, type_name: str, identifier: str) -> str:
        identifier_clean = identifier.strip()
        if type_name == "file":
            abs_path = os.path.abspath(os.path.expanduser(identifier_clean))
            return f"file://{abs_path}"
        elif type_name == "url":
            return f"url://{identifier_clean}"
        elif type_name == "terminal":
            abs_path = os.path.abspath(os.path.expanduser(identifier_clean))
            return f"terminal://{abs_path}"
        elif type_name == "repository":
            abs_path = os.path.abspath(os.path.expanduser(identifier_clean))
            return f"repository://{abs_path}"
        return f"{type_name}://{identifier_clean}"

    def register_file(self, file_path: str, repository: Optional[str] = None, line: Optional[int] = None, col: Optional[int] = None, display_name: Optional[str] = None, exists: Optional[bool] = None) -> ResourceItem:
        abs_path = os.path.abspath(os.path.expanduser(file_path))
        rid = f"file://{abs_path}"
        if exists is None:
            exists = os.path.exists(abs_path)
        d_name = display_name or os.path.basename(abs_path) or abs_path
        
        launch_cmd = f"code {abs_path}"
        if line is not None:
            launch_cmd = f"code -g {abs_path}:{line}"
            if col is not None:
                launch_cmd += f":{col}"

        item = ResourceItem(
            resource_id=rid,
            type="file",
            display_name=d_name,
            exists=exists,
            file=abs_path,
            repository=repository,
            launch_command=launch_cmd,
            metadata={"line": line, "col": col} if line is not None else {}
        )
        with self._lock:
            self._resources[rid] = item
        return item

    def register_url(self, url: str, title: Optional[str] = None) -> ResourceItem:
        rid = f"url://{url.strip()}"
        d_name = title or url
        item = ResourceItem(
            resource_id=rid,
            type="url",
            display_name=d_name,
            exists=True,
            url=url.strip(),
            launch_command=f"xdg-open {url.strip()}"
        )
        with self._lock:
            self._resources[rid] = item
        return item

    def register_terminal(self, cwd: str, recent_command: Optional[str] = None, repository: Optional[str] = None, exists: Optional[bool] = None) -> ResourceItem:
        abs_cwd = os.path.abspath(os.path.expanduser(cwd))
        rid = f"terminal://{abs_cwd}"
        if exists is None:
            exists = os.path.isdir(abs_cwd)
        d_name = f"Terminal ({os.path.basename(abs_cwd) or abs_cwd})"
        item = ResourceItem(
            resource_id=rid,
            type="terminal",
            display_name=d_name,
            exists=exists,
            terminal=recent_command,
            file=abs_cwd,
            repository=repository,
            metadata={"cwd": abs_cwd, "recent_command": recent_command}
        )
        with self._lock:
            self._resources[rid] = item
        return item

    def register_repository(self, repo_path: str, display_name: Optional[str] = None, exists: Optional[bool] = None) -> ResourceItem:
        abs_path = os.path.abspath(os.path.expanduser(repo_path))
        rid = f"repository://{abs_path}"
        if exists is None:
            exists = os.path.isdir(abs_path)
        d_name = display_name or os.path.basename(abs_path) or abs_path
        item = ResourceItem(
            resource_id=rid,
            type="repository",
            display_name=d_name,
            exists=exists,
            repository=abs_path,
            file=abs_path,
            launch_command=f"code {abs_path}"
        )
        with self._lock:
            self._resources[rid] = item
        return item

    def get_resource(self, resource_id: str) -> Optional[ResourceItem]:
        with self._lock:
            return self._resources.get(resource_id)

    def get_resources_by_type(self, type_name: str) -> List[ResourceItem]:
        with self._lock:
            return [res for res in self._resources.values() if res.type == type_name]

    def all_resources(self) -> List[ResourceItem]:
        with self._lock:
            return list(self._resources.values())
