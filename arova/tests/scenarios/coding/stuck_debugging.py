from arova.tests.scenarios.run_scenario import ScenarioDefinition, SimulatedEvent, ScenarioOutcome
from arova.core.models.registry import ArovaCapability, QualityTier

def get_scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        id="coding/stuck_debugging",
        name="Stuck Debugging Repetitive Errors",
        persona="Developer",
        events=[
            SimulatedEvent(
                app_name="terminal",
                window_title="bash - pytest arova/tests/",
                content_snippet="ModuleNotFoundError: No module named 'aiohttp' traceback",
                duration_s=45.0,
                tags=["terminal", "error"]
            ),
            SimulatedEvent(
                app_name="vscode",
                window_title="registry.py - Arova",
                content_snippet="import aiohttp # error loop check",
                duration_s=60.0,
                tags=["coding"]
            ),
            SimulatedEvent(
                app_name="terminal",
                window_title="bash - pytest arova/tests/",
                content_snippet="ModuleNotFoundError: No module named 'aiohttp'",
                duration_s=30.0,
                tags=["terminal", "error"]
            )
        ],
        expected_outcome=ScenarioOutcome(
            expected_workspace_keyword="Arova",
            expected_facts=[
                "aiohttp",
                "ModuleNotFoundError"
            ],
            expected_capability=ArovaCapability.AROVA_CAPABILITY_REASONING,
            expected_quality=QualityTier.PREMIUM
        )
    )
