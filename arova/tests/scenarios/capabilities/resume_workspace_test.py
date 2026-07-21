from arova.tests.scenarios.run_scenario import ScenarioDefinition, SimulatedEvent, ScenarioOutcome
from arova.core.models.registry import ArovaCapability, QualityTier

def get_scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        id="capabilities/resume_workspace_test",
        name="Capability Test: State Reconstruction across Boot",
        persona="System Test",
        events=[
            SimulatedEvent(
                app_name="vscode",
                window_title="memory_policy.py - Arova",
                content_snippet="def prune_expired_items(): # Blocker: testing privacy boundaries",
                duration_s=120.0,
                tags=["coding", "memory"]
            )
        ],
        expected_outcome=ScenarioOutcome(
            expected_workspace_keyword="memory_policy.py",
            expected_facts=[
                "memory_policy.py",
                "privacy boundaries"
            ],
            expected_capability=ArovaCapability.AROVA_CAPABILITY_RESUME_WORKSPACE,
            expected_quality=QualityTier.BALANCED
        )
    )
