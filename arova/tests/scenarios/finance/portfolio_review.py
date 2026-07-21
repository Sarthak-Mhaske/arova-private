from arova.tests.scenarios.run_scenario import ScenarioDefinition, SimulatedEvent, ScenarioOutcome
from arova.core.models.registry import ArovaCapability, QualityTier

def get_scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        id="finance/portfolio_review",
        name="Quarterly Portfolio & Tax Review",
        persona="Financial Analyst",
        events=[
            SimulatedEvent(
                app_name="excel",
                window_title="Q3_Portfolio_Holdings.xlsx - Microsoft Excel",
                content_snippet="Asset Allocation: Equities 65%, Bonds 25%, Crypto 10%. Rebalancing threshold breached.",
                duration_s=240.0,
                tags=["spreadsheet", "finance"]
            ),
            SimulatedEvent(
                app_name="chrome",
                window_title="Bloomberg - Market Indices & Treasury Yields",
                content_snippet="10-year Treasury yield rises to 4.2%. Tech sector valuation metrics.",
                duration_s=180.0,
                tags=["finance", "news"]
            )
        ],
        expected_outcome=ScenarioOutcome(
            expected_workspace_keyword="Portfolio",
            expected_facts=[
                "Equities",
                "Rebalancing"
            ],
            expected_capability=ArovaCapability.AROVA_CAPABILITY_SUMMARIZE,
            expected_quality=QualityTier.BALANCED
        )
    )
