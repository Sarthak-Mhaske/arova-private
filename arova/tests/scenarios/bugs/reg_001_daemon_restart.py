from arova.tests.scenarios.run_scenario import ScenarioDefinition, SimulatedEvent, ScenarioOutcome
from arova.core.models.registry import ArovaCapability, QualityTier

def get_scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        id="bugs/001_daemon_restart",
        name="Regression 001: Daemon Supervisor Restart Resilience",
        persona="System Regression",
        events=[
            SimulatedEvent(
                app_name="vscode",
                window_title="supervisor.py - Arova",
                content_snippet="def restart_daemon(): # recovery from SIGKILL",
                duration_s=30.0,
                tags=["system", "recovery"]
            )
        ],
        expected_outcome=ScenarioOutcome(
            expected_workspace_keyword="supervisor.py",
            expected_facts=[
                "supervisor.py",
                "restart_daemon"
            ],
            expected_capability=ArovaCapability.AROVA_CAPABILITY_RESUME_WORKSPACE,
            expected_quality=QualityTier.BALANCED
        )
    )
