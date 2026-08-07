"""
RestorePlanner — converts cognitive workspace resources into RestoreIntents.

The planner bridges the cognitive layer (`CognitiveWorkspace`) and the platform
services layer (`CapabilityRegistry`).  It classifies each resource by kind,
looks up preferred applications from ApplicationAffinity (not MIME defaults),
assigns priorities, and returns a reviewable LaunchPlan.

The planner answers: 'What is the user trying to get back?'
It never knows about OS launch commands or subprocess execution.
"""
import os
import time
import shutil
import logging
from typing import Dict, Any, Optional, List, Set, Tuple

from arova.core.platform.services.capabilities import Capability
from arova.core.platform.services.intents import RestoreIntent, LaunchPlan
from arova.core.platform.services.catalog import ApplicationCatalog
from arova.core.platform.services.affinity import ApplicationAffinity

logger = logging.getLogger(__name__)


class RestorePlanner:
    """
    Plans environment restoration by translating workspace reality into a LaunchPlan.
    """

    def __init__(self, catalog: ApplicationCatalog, affinity: ApplicationAffinity):
        self.catalog = catalog
        self.affinity = affinity

    def plan(self, workspace: Any, options: Optional[Dict[str, Any]] = None, resource_registry_items: Optional[List[Any]] = None) -> LaunchPlan:
        """
        Produce an ordered LaunchPlan from the given cognitive workspace and existing resource items.
        """
        options = options or {}
        resource_registry_items = resource_registry_items or []
        wid = getattr(workspace, "workspace_id", "unknown")
        title = getattr(workspace, "title", "Workspace")
        intents: List[RestoreIntent] = []
        seen_keys: Set[Tuple[str, str]] = set()  # (kind, path)
        seen_urls: Set[str] = set()

        logger.info(f"RestorePlanner: Generating LaunchPlan for workspace '{title}' ({wid}) with options {options}")

        reality = getattr(workspace, "reality", None)
        resources_dict = getattr(reality, "resources", {}) if reality else {}

        restore_files = options.get("restore_vscode", options.get("restore_editors", True))
        restore_terminal = options.get("restore_terminal", True)
        restore_browsers = options.get("restore_chrome", options.get("restore_browsers", False))
        selected_urls = options.get("selected_urls", [])

        # 1. Check repository paths from interpretation layer first (priority 1)
        interpretation = getattr(workspace, "interpretation", None)
        repo_paths = getattr(interpretation, "repo_paths", []) if interpretation else []
        for rp in repo_paths:
            if not rp:
                continue
            abs_rp = os.path.abspath(os.path.expanduser(rp))
            if os.path.isdir(abs_rp) or abs_rp == os.path.expanduser("~/arova"):
                key = ("repository", abs_rp)
                if key not in seen_keys:
                    seen_keys.add(key)
                    pref_app = self._get_preferred_app_for_folder(abs_rp)
                    intents.append(RestoreIntent(
                        kind="repository",
                        capability=Capability.OPEN_FOLDER,
                        resource_path=abs_rp,
                        preferred_application=pref_app,
                        confidence=1.0,
                        priority=1
                    ))

        # Also check repository items from resource_registry_items
        for item in resource_registry_items:
            if getattr(item, "type", "") == "repository" and getattr(item, "exists", False):
                abs_rp = os.path.abspath(os.path.expanduser(item.repository))
                key = ("repository", abs_rp)
                if key not in seen_keys:
                    seen_keys.add(key)
                    pref_app = self._get_preferred_app_for_folder(abs_rp)
                    intents.append(RestoreIntent(
                        kind="repository",
                        capability=Capability.OPEN_FOLDER,
                        resource_path=abs_rp,
                        preferred_application=pref_app,
                        confidence=1.0,
                        priority=1
                    ))

        # 2. Iterate reality resources
        for key_id, res_meta in resources_dict.items():
            if not isinstance(res_meta, dict):
                continue
            r_type = res_meta.get("type", "file")
            identity = res_meta.get("identity", key_id)

            if r_type == "repository" or identity.startswith("repository://"):
                clean_path = identity.replace("repository://", "")
                abs_path = os.path.abspath(os.path.expanduser(clean_path))
                key = ("repository", abs_path)
                if key not in seen_keys:
                    seen_keys.add(key)
                    pref_app = self._get_preferred_app_for_folder(abs_path)
                    intents.append(RestoreIntent(
                        kind="repository",
                        capability=Capability.OPEN_FOLDER,
                        resource_path=abs_path,
                        preferred_application=pref_app,
                        confidence=1.0,
                        priority=1
                    ))

            elif r_type == "file" or identity.startswith("/") or identity.startswith("file://"):
                if not restore_files:
                    continue
                clean_path = identity.replace("file://", "")
                abs_path = os.path.abspath(os.path.expanduser(clean_path))
                key = ("source_file", abs_path)
                if key not in seen_keys:
                    seen_keys.add(key)
                    line = res_meta.get("line")
                    col = res_meta.get("col")
                    pref_app = self._get_preferred_app_for_file(abs_path)
                    intents.append(RestoreIntent(
                        kind="source_file",
                        capability=Capability.OPEN_FILE,
                        resource_path=abs_path,
                        preferred_application=pref_app,
                        confidence=0.96,
                        metadata={"line": line, "col": col} if line is not None else {},
                        priority=2
                    ))

            elif r_type == "terminal" or identity.startswith("terminal://"):
                if not restore_terminal:
                    continue
                clean_path = identity.replace("terminal://", "")
                abs_path = os.path.abspath(os.path.expanduser(clean_path))
                key = ("terminal", abs_path)
                if key not in seen_keys:
                    seen_keys.add(key)
                    recent_cmd = res_meta.get("recent_command") or (res_meta.get("identity") if res_meta.get("identity") != abs_path else None)
                    intents.append(RestoreIntent(
                        kind="terminal",
                        capability=Capability.CREATE_TERMINAL,
                        resource_path=abs_path,
                        confidence=0.95,
                        metadata={"recent_command": recent_cmd, "cwd": abs_path},
                        priority=3
                    ))

            elif r_type in ["url", "browser"] or identity.startswith("http") or identity.startswith("url://"):
                clean_url = identity.replace("url://", "").strip()
                is_selected = restore_browsers or (clean_url in selected_urls) or (res_meta.get("summary") in selected_urls)
                if is_selected and clean_url not in seen_urls:
                    seen_urls.add(clean_url)
                    pref_app = self._get_preferred_app_for_url(clean_url)
                    intents.append(RestoreIntent(
                        kind="documentation",
                        capability=Capability.OPEN_URL,
                        resource_url=clean_url,
                        preferred_application=pref_app,
                        confidence=0.90,
                        priority=4
                    ))

        # 3. Also check files and terminals from resource_registry_items
        for item in resource_registry_items:
            r_type = getattr(item, "type", "")
            if r_type == "file" and restore_files and getattr(item, "exists", False):
                abs_path = os.path.abspath(os.path.expanduser(item.file))
                key = ("source_file", abs_path)
                if key not in seen_keys:
                    seen_keys.add(key)
                    line = item.metadata.get("line")
                    col = item.metadata.get("col")
                    pref_app = self._get_preferred_app_for_file(abs_path)
                    intents.append(RestoreIntent(
                        kind="source_file",
                        capability=Capability.OPEN_FILE,
                        resource_path=abs_path,
                        preferred_application=pref_app,
                        confidence=0.96,
                        metadata={"line": line, "col": col} if line is not None else {},
                        priority=2
                    ))
            elif r_type == "terminal" and restore_terminal:
                abs_path = os.path.abspath(os.path.expanduser(item.file or item.metadata.get("cwd", "/")))
                key = ("terminal", abs_path)
                if key not in seen_keys:
                    seen_keys.add(key)
                    recent_cmd = getattr(item, "terminal", None) or item.metadata.get("recent_command")
                    intents.append(RestoreIntent(
                        kind="terminal",
                        capability=Capability.CREATE_TERMINAL,
                        resource_path=abs_path,
                        confidence=0.95,
                        metadata={"recent_command": recent_cmd, "cwd": abs_path},
                        priority=3
                    ))
            elif r_type == "url":
                clean_url = getattr(item, "url", "").strip()
                is_selected = restore_browsers or (clean_url in selected_urls) or (getattr(item, "display_name", "") in selected_urls)
                if is_selected and clean_url not in seen_urls:
                    seen_urls.add(clean_url)
                    pref_app = self._get_preferred_app_for_url(clean_url)
                    intents.append(RestoreIntent(
                        kind="documentation",
                        capability=Capability.OPEN_URL,
                        resource_url=clean_url,
                        preferred_application=pref_app,
                        confidence=0.90,
                        priority=4
                    ))

        # 4. If browser restoration requested, also check browser domains from interpretation
        if restore_browsers and interpretation:
            domains = getattr(interpretation, "browser_domains", [])
            for domain in domains:
                url = f"https://{domain}" if not domain.startswith("http") else domain
                if url not in seen_urls and not any(d in seen_urls for d in [url, domain]):
                    seen_urls.add(url)
                    pref_app = self._get_preferred_app_for_url(url)
                    intents.append(RestoreIntent(
                        kind="documentation",
                        capability=Capability.OPEN_URL,
                        resource_url=url,
                        preferred_application=pref_app,
                        confidence=0.85,
                        priority=4
                    ))

        # 5. If terminal restoration requested and no terminal intent exists yet, derive from repo
        if restore_terminal and not any(i.kind == "terminal" for i in intents):
            repo_intent = next((i for i in intents if i.kind == "repository" and i.resource_path), None)
            if repo_intent:
                intents.append(RestoreIntent(
                    kind="terminal",
                    capability=Capability.CREATE_TERMINAL,
                    resource_path=repo_intent.resource_path,
                    confidence=0.95,
                    metadata={"cwd": repo_intent.resource_path},
                    priority=3
                ))

        auto_approve = options.get("auto_approve", False)
        return LaunchPlan(
            workspace_id=wid,
            workspace_title=title,
            intents=intents,
            timestamp=time.time(),
            approved=auto_approve
        )

    def _get_preferred_app_for_file(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1]
        if ext:
            aff_app = self.affinity.get_preferred_app(ext)
            if aff_app:
                return aff_app

        handler = self.catalog.find_handler_for_file(file_path)
        if handler and handler.executable and "gnome-software" not in handler.executable:
            return os.path.basename(handler.executable)

        for code_app in ("code", "cursor", "idea"):
            if self.catalog.get_application(code_app) or shutil.which(code_app):
                return code_app

        editor = self.catalog.get_default_editor()
        if editor and editor.executable and "gnome-software" not in editor.executable:
            return os.path.basename(editor.executable)

        return "code"

    def _get_preferred_app_for_folder(self, folder_path: str) -> str:
        aff_app = self.affinity.get_preferred_app(".project") or self.affinity.get_preferred_app(".folder")
        if aff_app:
            return aff_app
        for code_app in ("code", "cursor", "idea"):
            if self.catalog.get_application(code_app) or shutil.which(code_app):
                return code_app
        editor = self.catalog.get_default_editor()
        if editor and editor.executable and "gnome-software" not in editor.executable:
            return os.path.basename(editor.executable)
        return "code"

    def _get_preferred_app_for_url(self, url: str) -> str:
        aff_app = self.affinity.get_preferred_app(".html") or self.affinity.get_preferred_app(".url")
        if aff_app:
            return aff_app
        browser = self.catalog.get_default_browser()
        if browser and browser.executable:
            return os.path.basename(browser.executable)
        return ""
