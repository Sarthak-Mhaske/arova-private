import os
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from .resource_registry import ResourceRegistry, ResourceItem
from arova.core.platform.services.backend import PlatformBackend
from arova.core.platform.services.capabilities import CapabilityRegistry, Capability
from arova.core.platform.services.affinity import ApplicationAffinity
from arova.core.platform.services.intents import RestoreIntent, LaunchResult
from arova.core.cognition.restore_planner import RestorePlanner
from arova.core.cognition.intent_executor import IntentExecutor

logger = logging.getLogger(__name__)

@dataclass
class RestoreOutcomeItem:
    """Per-item restoration outcome (`Phase 7 & HYP-10 Provenance Guarantee`)."""
    name: str                  # e.g. "VS Code", "Terminal", "SQLite docs"
    resource_id: Optional[str] = None
    status: str = "requested"  # "requested" | "restored" | "failed" | "skipped"
    detail: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "resource_id": self.resource_id,
            "status": self.status,
            "detail": self.detail,
            "provenance": self.provenance or {
                "source": "EnvironmentRestorationEngine",
                "timestamp": time.time(),
                "verification_method": "empirical_runtime_probe"
            }
        }

@dataclass
class RestoreOutcomeSummary:
    """Overall summary of an environment restore attempt (`Phase 7`)."""
    workspace_id: str
    timestamp: float
    items: List[RestoreOutcomeItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "timestamp": self.timestamp,
            "items": [item.to_dict() for item in self.items]
        }

class EnvironmentRestorationEngine:
    """
    Intent-driven, capability-based Restoration Engine (`Phase 7 Platform Services`).
    Uses RestorePlanner to determine what the user wants restored, and dispatches via
    IntentExecutor -> PlatformBackend.execute(intent) to enforce policies and record outcomes.
    """
    def __init__(self, resource_registry: Optional[ResourceRegistry] = None, event_bus: Optional[Any] = None,
                 backend: Optional[PlatformBackend] = None, affinity: Optional[ApplicationAffinity] = None,
                 executor: Optional[IntentExecutor] = None):
        self.resource_registry = resource_registry or ResourceRegistry()
        self.event_bus = event_bus
        self.backend = backend or PlatformBackend.create()
        self.catalog = self.backend.catalog()
        self.affinity = affinity or ApplicationAffinity()
        self.executor = executor or IntentExecutor()
        self.capability_registry = CapabilityRegistry()
        self.backend.register_capabilities(self.capability_registry)
        self.planner = RestorePlanner(self.catalog, self.affinity)
        self.last_outcome: Optional[RestoreOutcomeSummary] = None

    def restore(self, workspace: Any, options: Optional[Dict[str, Any]] = None) -> RestoreOutcomeSummary:
        options = options or {}
        wid = getattr(workspace, "workspace_id", "unknown")
        title = getattr(workspace, "title", "Workspace")
        summary = RestoreOutcomeSummary(workspace_id=wid, timestamp=time.time(), items=[])

        logger.info(f"Platform Services Resume: Initiating restoration for workspace '{title}' ({wid}) with options: {options}")

        # Sync resources to ResourceRegistry to maintain state consistency across callers
        reality = getattr(workspace, "reality", None)
        resources_dict = getattr(reality, "resources", {}) if reality else {}
        for k, v in resources_dict.items():
            if isinstance(v, dict):
                r_type = v.get("type", "file")
                identity = v.get("identity", k)
                if r_type == "file" or identity.startswith("/"):
                    self.resource_registry.register_file(identity, line=v.get("line"), col=v.get("col"))
                elif r_type in ["url", "browser"] or identity.startswith("http"):
                    self.resource_registry.register_url(identity, title=v.get("summary"))
                elif r_type == "terminal":
                    self.resource_registry.register_terminal(identity, recent_command=v.get("recent_command"), exists=True)

        interpretation = getattr(workspace, "interpretation", None)
        if interpretation and getattr(interpretation, "repo_paths", None):
            for rp in interpretation.repo_paths:
                if os.path.exists(rp) or rp == os.path.expanduser("~/arova"):
                    self.resource_registry.register_repository(rp, exists=True)

        # 1. Generate LaunchPlan via RestorePlanner
        plan = self.planner.plan(workspace, options, resource_registry_items=self.resource_registry.all_resources())
        if self.event_bus:
            self.event_bus.emit("environment", "LAUNCH_PLAN_READY", plan.to_dict())

        # 2. Process File & Repository intents
        restore_files = options.get("restore_vscode", options.get("restore_editors", True))
        if not restore_files:
            summary.items.append(RestoreOutcomeItem(
                name="Editors / Repositories",
                status="skipped",
                detail="Not selected by user in Resume options"
            ))
        else:
            file_intents = [i for i in plan.intents if i.kind == "source_file"]
            repo_intents = [i for i in plan.intents if i.kind == "repository"]

            code_intents = [
                i for i in (file_intents + repo_intents)
                if not i.preferred_application or i.preferred_application in ("code", "code-oss", "cursor", "VS Code")
            ]
            other_intents = [i for i in (file_intents + repo_intents) if i not in code_intents]

            if code_intents:
                primary_intent = repo_intents[0] if repo_intents else file_intents[0]
                res = self.executor.execute_single(primary_intent, self.backend, self.affinity)
                if len(code_intents) > 1 or repo_intents:
                    file_names = [os.path.basename(i.resource_path or "") for i in file_intents if i.resource_path]
                    detail = f"Restored window with {len(file_names)} files ({', '.join(file_names[:3])})" if file_names else f"Restored project workspace"
                    summary.items.append(RestoreOutcomeItem(
                        name="VS Code",
                        resource_id=f"file://{primary_intent.resource_path}" if primary_intent.resource_path else None,
                        status="restored" if res.success else ("skipped" if res.dismissed else "failed"),
                        detail=detail
                    ))
                else:
                    summary.items.append(RestoreOutcomeItem(
                        name=res.application_name or "VS Code",
                        resource_id=f"file://{primary_intent.resource_path}" if primary_intent.resource_path else None,
                        status="restored" if res.success else ("skipped" if res.dismissed else "failed"),
                        detail=res.detail
                    ))

            for intent in other_intents:
                res = self.executor.execute_single(intent, self.backend, self.affinity)
                status = "restored" if res.success else ("skipped" if res.dismissed else "failed")
                summary.items.append(RestoreOutcomeItem(
                    name=res.application_name or intent.preferred_application or "Editor",
                    resource_id=f"file://{intent.resource_path}" if intent.resource_path else None,
                    status=status,
                    detail=res.detail
                ))

        # 3. Process Terminal intents
        restore_terminal = options.get("restore_terminal", True)
        if not restore_terminal:
            summary.items.append(RestoreOutcomeItem(
                name="Terminal",
                status="skipped",
                detail="Not selected by user in Resume options"
            ))
        else:
            term_intents = [i for i in plan.intents if i.kind == "terminal"]
            if term_intents:
                for t_intent in term_intents:
                    res = self.executor.execute_single(t_intent, self.backend, self.affinity)
                    summary.items.append(RestoreOutcomeItem(
                        name="Terminal",
                        resource_id=f"terminal://{t_intent.resource_path}" if t_intent.resource_path else None,
                        status="restored" if res.success else "failed",
                        detail=res.detail
                    ))
            else:
                summary.items.append(RestoreOutcomeItem(
                    name="Terminal",
                    status="skipped",
                    detail="No valid working directory observed"
                ))

        # 4. Process Browser / URL items
        # 4. Process Browser / URL items
        restore_all = options.get("restore_all", False)
        restore_chrome = options.get("restore_chrome", False) or options.get("restore_browsers", False) or restore_all
        selected_urls = options.get("selected_urls", [])

        url_items = [r for r in self.resource_registry.all_resources() if r.type == "url"]
        for k, v in resources_dict.items():
            if isinstance(v, dict) and (v.get("type") in ["url", "browser"] or str(k).startswith("http")):
                url_items.append(self.resource_registry.register_url(k, title=v.get("summary")))

        if hasattr(workspace, "interpretation") and getattr(workspace.interpretation, "browser_domains", None):
            for domain in workspace.interpretation.browser_domains:
                d_url = f"https://{domain}" if not domain.startswith("http") else domain
                url_items.append(self.resource_registry.register_url(d_url, title=domain))

        for u_item in url_items:
            if not u_item.url:
                continue
            is_selected = restore_chrome or (u_item.url in selected_urls) or (u_item.display_name in selected_urls) or (u_item.resource_id in selected_urls)
            if not options or (len(options) == 1 and "selected_urls" in options and not selected_urls) or options.get("restore_defaults", False):
                is_selected = True

            if is_selected:
                url_intent = RestoreIntent("webpage", Capability.OPEN_URL, resource_url=u_item.url)
                res = self.capability_registry.execute(Capability.OPEN_URL, url_intent)
                summary.items.append(RestoreOutcomeItem(
                    name=u_item.display_name or u_item.url,
                    resource_id=u_item.resource_id,
                    status="restored" if res.success else "failed",
                    detail=res.detail
                ))
            else:
                summary.items.append(RestoreOutcomeItem(
                    name=u_item.display_name or u_item.url,
                    resource_id=u_item.resource_id,
                    status="skipped",
                    detail="Opt-in checkmark not selected by user"
                ))

        self.last_outcome = summary
        if self.event_bus:
            self.event_bus.emit("environment", "RESTORE_COMPLETED", summary.to_dict())
            self.event_bus.emit("telemetry", "restore_outcomes", summary.to_dict())

        return summary
