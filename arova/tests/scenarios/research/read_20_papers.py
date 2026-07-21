from arova.tests.scenarios.run_scenario import ScenarioDefinition, SimulatedEvent, ScenarioOutcome
from arova.core.models.registry import ArovaCapability, QualityTier

def get_scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        id="research/read_20_papers",
        name="Intensive Literature Review (Attention & Memory Architecture)",
        persona="Researcher",
        events=[
            SimulatedEvent(
                app_name="pdf_reader",
                window_title="Vaswani et al. - Attention Is All You Need.pdf",
                content_snippet="We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.",
                duration_s=300.0,
                tags=["pdf", "research"]
            ),
            SimulatedEvent(
                app_name="chrome",
                window_title="Google Scholar - Cognitive Architectures in AI",
                content_snippet="Citations and related literature on episodic memory and working memory models.",
                duration_s=150.0,
                tags=["research", "scholar"]
            ),
            SimulatedEvent(
                app_name="notion",
                window_title="Literature Review Notes - Notion",
                content_snippet="Key findings: Transformers lack long-term persistent working memory without external substrate.",
                duration_s=180.0,
                tags=["notes", "research"]
            )
        ],
        expected_outcome=ScenarioOutcome(
            expected_workspace_keyword="Literature",
            expected_facts=[
                "Attention Is All You Need",
                "Transformer",
                "working memory"
            ],
            expected_capability=ArovaCapability.AROVA_CAPABILITY_SUMMARIZE,
            expected_quality=QualityTier.BALANCED
        )
    )
