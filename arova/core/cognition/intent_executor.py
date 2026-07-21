"""
IntentExecutor — applies cognitive execution policies before invoking PlatformBackend.

Separates execution policies (user approval gates, batch limits, permissions checks,
window reuse rules, and telemetry/affinity loops) from OS platform implementation code.
The cognitive layer dispatches through IntentExecutor -> PlatformBackend.execute(intent).
"""
import os
import logging
from typing import List, Optional, Any

from arova.core.platform.services.capabilities import Capability
from arova.core.platform.services.intents import RestoreIntent, LaunchPlan, LaunchResult
from arova.core.platform.services.backend import PlatformBackend
from arova.core.platform.services.affinity import ApplicationAffinity

logger = logging.getLogger(__name__)


class IntentExecutor:
    """
    Enforces execution policies and manages the post-launch telemetry feedback loop.

    Flow:
        RestoreIntent -> LaunchPlan -> IntentExecutor -> PlatformBackend.execute(intent)
    """

    def __init__(self, max_batch_without_prompt: int = 10):
        self.max_batch_without_prompt = max_batch_without_prompt

    def execute_plan(self, plan: LaunchPlan, backend: PlatformBackend,
                     affinity: Optional[ApplicationAffinity] = None) -> List[LaunchResult]:
        """
        Execute all intents in a reviewable LaunchPlan according to cognitive execution policies.
        """
        results: List[LaunchResult] = []

        # 1. Policy check: Batch limits without approval
        if not plan.approved and len(plan.intents) > self.max_batch_without_prompt:
            logger.warning(f"IntentExecutor: Plan has {len(plan.intents)} intents (exceeds limit {self.max_batch_without_prompt} without approval). Requiring explicit approval.")
            for intent in plan.intents:
                results.append(LaunchResult(
                    intent=intent,
                    success=False,
                    application_name="",
                    detail="Skipped execution: batch size exceeds prompt threshold without explicit user approval.",
                    executed=False
                ))
            return results

        # Sort by priority (priority 1 first)
        ordered_intents = sorted(plan.intents, key=lambda i: i.priority)

        for intent in ordered_intents:
            res = self.execute_single(intent, backend, affinity)
            results.append(res)

        return results

    def execute_single(self, intent: RestoreIntent, backend: PlatformBackend,
                       affinity: Optional[ApplicationAffinity] = None) -> LaunchResult:
        """
        Execute a single RestoreIntent, enforcing permission checks, dismissal gates, and recording outcomes.
        """
        # 1.5. Policy check: Dismissed by user during plan review
        if intent.metadata.get("dismissed") is True:
            logger.info(f"IntentExecutor: Intent {intent.kind} ({intent.resource_path or intent.resource_url}) was dismissed by user.")
            res = LaunchResult(
                intent=intent,
                success=False,
                application_name=intent.preferred_application or "",
                detail="Dismissed by user during plan review",
                executed=False,
                dismissed=True
            )
            if affinity is not None:
                ext_key = self._derive_resource_key(intent)
                app_id_or_name = intent.app_id or intent.preferred_application
                if app_id_or_name:
                    affinity.record_outcome(ext_key, app_id_or_name, positive=False, weight=1)
                    logger.debug(f"IntentExecutor: Recorded dismissed outcome (-1) for '{app_id_or_name}' on '{ext_key}'")
            return res

        # 2. Policy check: Permissions validation
        perms = backend.permissions()
        if intent.capability == Capability.CREATE_TERMINAL:
            # Terminals / shells may require explicit permission check depending on sandbox
            if hasattr(perms, "check_screen_capture") and not perms.check_screen_capture():
                logger.warning(f"IntentExecutor: Permission denied when checking environment access for terminal launch.")
                return LaunchResult(
                    intent=intent,
                    success=False,
                    application_name="",
                    detail="Permission check failed before launching terminal.",
                    executed=False,
                    error="Permission denied"
                )

        # 3. Dispatch to PlatformBackend facade
        try:
            res = backend.execute(intent)
        except Exception as e:
            logger.error(f"IntentExecutor: Backend execute exception for {intent.kind}: {e}", exc_info=True)
            res = LaunchResult(
                intent=intent,
                success=False,
                application_name=intent.preferred_application or "",
                detail=f"Backend execution exception: {e}",
                executed=True,
                error=str(e)
            )

        # 4. Telemetry & Affinity feedback loop (record_outcome)
        if affinity is not None:
            ext_key = self._derive_resource_key(intent)
            app_id_or_name = res.app_id or intent.app_id or res.application_name or intent.preferred_application
            if app_id_or_name:
                if res.dismissed:
                    affinity.record_outcome(ext_key, app_id_or_name, positive=False, weight=1)
                    logger.debug(f"IntentExecutor: Recorded dismissed outcome (-1) for '{app_id_or_name}' on '{ext_key}'")
                elif res.success:
                    # Positive outcome (Affinity++)
                    weight = 2 if (res.focused or res.actually_used) else 1
                    affinity.record_outcome(ext_key, app_id_or_name, positive=True, weight=weight)
                    logger.debug(f"IntentExecutor: Recorded positive outcome (+{weight}) for '{app_id_or_name}' on '{ext_key}'")
                else:
                    # Negative outcome (Affinity--)
                    affinity.record_outcome(ext_key, app_id_or_name, positive=False, weight=1)
                    logger.debug(f"IntentExecutor: Recorded negative outcome (-1) for '{app_id_or_name}' on '{ext_key}'")

        return res

    def _derive_resource_key(self, intent: RestoreIntent) -> str:
        if intent.resource_path:
            ext = os.path.splitext(intent.resource_path)[1]
            if ext:
                return ext.lower()
        if intent.kind == "webpage" or intent.resource_url:
            return "url"
        if intent.kind == "terminal":
            return "terminal"
        if intent.kind == "repository":
            return "repository"
        return intent.kind.lower()
