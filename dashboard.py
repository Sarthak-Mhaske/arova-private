import sys
from collections import defaultdict
from typing import Dict, Any

class ArovaDashboard:
    """
    A lightweight internal operations dashboard for Arova's proactive pipeline.
    Connects to KPITelemetryCollector and prints the daily value report.
    """
    def __init__(self, metrics_data: Dict[str, Any]):
        self.metrics = metrics_data

    def generate_report(self):
        print("="*60)
        print(" AROVA DAILY VALUE DASHBOARD ")
        print("="*60)
        
        # Aggregate logic
        total_interventions = len(self.metrics.get("proactive_interventions", []))
        outcomes = defaultdict(int)
        total_est_nwr = 0.0
        total_obs_nwr = 0.0
        
        workflows = defaultdict(lambda: {"total": 0, "accepted": 0, "nwr": 0.0, "fp": 0})
        
        for inv in self.metrics.get("proactive_interventions", []):
            outcome = inv.get("outcome", "unknown")
            outcomes[outcome] += 1
            wf = inv.get("workflow", "unknown")
            workflows[wf]["total"] += 1
            
            total_est_nwr += inv.get("estimated_nwr", 0.0)
            total_obs_nwr += inv.get("observed_nwr", 0.0)
            
            if outcome == "accepted":
                workflows[wf]["accepted"] += 1
                workflows[wf]["nwr"] += inv.get("observed_nwr", 0.0)
            elif outcome == "dismissed":
                workflows[wf]["fp"] += 1

        accepted = outcomes["accepted"]
        dismissed = outcomes["dismissed"]
        ignored = outcomes["ignored"]
        
        # Calculate Rates
        acc_rate = (accepted / total_interventions * 100) if total_interventions > 0 else 0.0
        fp_rate = (dismissed / total_interventions * 100) if total_interventions > 0 else 0.0
        
        correct_silence = self.metrics.get("correct_silence_count", 0)
        missed_opp = self.metrics.get("missed_opportunity_count", 0)
        silence_total = correct_silence + missed_opp
        correct_silence_rate = (correct_silence / silence_total * 100) if silence_total > 0 else 100.0

        print(f"\nInvestigations Started : {total_interventions}")
        print(f"Completed Work         : {total_interventions - outcomes['verification_failed']}")
        print(f"Accepted               : {accepted}")
        print(f"Dismissed (FP)         : {dismissed}")
        print(f"Ignored                : {ignored}")
        print(f"Superseded             : {outcomes['superseded']}")
        print(f"Failed Verification    : {outcomes['verification_failed']}")
        
        print("\n--- Value & Accuracy ---")
        print(f"Daily Work Removed (Observed) : {total_obs_nwr:.1f} minutes")
        print(f"Estimated NWR                 : {total_est_nwr:.1f} minutes")
        print(f"Acceptance Rate               : {acc_rate:.1f}%")
        print(f"False Positive Rate           : {fp_rate:.1f}%")
        print(f"Correct Silence Rate          : {correct_silence_rate:.1f}%")

        print("\n--- Workflow Segmentation ---")
        print(f"{'Workflow':<15} | {'Acceptance':<10} | {'Avg NWR':<10} | {'False Positives'}")
        print("-" * 55)
        for wf, stats in workflows.items():
            if stats["total"] > 0:
                wf_acc = (stats["accepted"] / stats["total"]) * 100
                wf_fp = (stats["fp"] / stats["total"]) * 100
                wf_nwr = (stats["nwr"] / stats["accepted"]) if stats["accepted"] > 0 else 0.0
                print(f"{wf:<15} | {wf_acc:>8.1f}% | {wf_nwr:>6.1f} min | {wf_fp:>13.1f}%")

        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    # Mock data injection for the script standalone run
    mock_data = {
        "proactive_interventions": [
            {"workflow": "fix", "outcome": "accepted", "estimated_nwr": 12.0, "observed_nwr": 15.0},
            {"workflow": "fix", "outcome": "accepted", "estimated_nwr": 5.0, "observed_nwr": 6.0},
            {"workflow": "fix", "outcome": "dismissed", "estimated_nwr": 10.0, "observed_nwr": 0.0},
            {"workflow": "investigate", "outcome": "ignored", "estimated_nwr": 8.0, "observed_nwr": 0.0},
            {"workflow": "summarize", "outcome": "accepted", "estimated_nwr": 4.0, "observed_nwr": 3.0},
        ],
        "correct_silence_count": 92,
        "missed_opportunity_count": 8
    }
    dashboard = ArovaDashboard(mock_data)
    dashboard.generate_report()
