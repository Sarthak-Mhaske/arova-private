from arova.tests.scenarios.run_scenario import ScenarioDefinition, SimulatedEvent, ScenarioOutcome
from arova.core.models.registry import ArovaCapability, QualityTier

def get_scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        id="coding/resume_python_project",
        name="Resume Python Project (VSCode)",
        persona="Developer",
        events=[
            SimulatedEvent(
                app_name="vscode",
                window_title="runtime.py - Arova - Visual Studio Code",
                content_snippet="class ModelRuntime: def _select_model(self, depth):",
                duration_s=120.0,
                tags=["coding", "python"]
            ),
            SimulatedEvent(
                app_name="vscode",
                window_title="workspace.py - Arova - Visual Studio Code",
                content_snippet="class WorkspaceManager: def process_context(self): # Blocker: SQLite persistence",
                duration_s=300.0,
                tags=["coding", "python"]
            ),
            SimulatedEvent(
                app_name="chrome",
                window_title="SQLite persistence docs - Groq API Reference",
                content_snippet="How to safely persist context vectors using SQLite and Tier 3 consent.",
                duration_s=90.0,
                tags=["documentation"]
            )
        ],
        expected_outcome=ScenarioOutcome(
            expected_workspace_keyword="Arova",
            expected_facts=[
                "Arova",
                "SQLite persistence",
                "Workspace"
            ],
            expected_capability=ArovaCapability.AROVA_CAPABILITY_RESUME_WORKSPACE,
            expected_quality=QualityTier.BALANCED
        )
    )
