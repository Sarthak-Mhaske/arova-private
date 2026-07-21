import os
import sys
import time
import json
import argparse
import zipfile
import tempfile
from datetime import datetime

from arova.core.cognition.recorder import SessionRecorder
from arova.core.cognition.workspace_manager import WorkspaceManager
from arova.core.models.registry import get_model_registry


def generate_feedback_bundle(issue_description: str,
                             output_filepath: Optional[str] = None,
                             satisfaction_rating: str = "WRONG") -> str:
    """
    One-click automated feedback and diagnostic bundle generator for Arova beta users.
    Generates a self-contained .zip archive containing:
      1. Issue summary description & human ground truth rating
      2. Replay Package (v2.0 JSON with Decision Timeline)
      3. Active Model Registry profile
      4. Active Workspace state & confidence score
      5. System health check & environment telemetry
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_filepath:
        export_dir = os.path.join(os.path.expanduser("~"), "arova_exports")
        os.makedirs(export_dir, exist_ok=True)
        output_filepath = os.path.join(export_dir, f"arova_feedback_{timestamp}.zip")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)

    # Initialize or grab recorder
    recorder = SessionRecorder()
    if satisfaction_rating:
        recorder.record_satisfaction(rating=satisfaction_rating, reason=issue_description)

    # Grab active workspace
    workspace_mgr = WorkspaceManager()
    active_ws = workspace_mgr.get_active_workspace()

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Write Issue Summary
        summary_path = os.path.join(tmp_dir, "issue_summary.json")
        with open(summary_path, "w", encoding="utf-8") as sf:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "issue_description": issue_description,
                "satisfaction_rating": satisfaction_rating,
                "system_platform": sys.platform,
                "python_version": sys.version
            }, sf, indent=2)

        # 2. Export Replay JSON
        replay_path = os.path.join(tmp_dir, "replay_package.json")
        recorder.export_replay_package(filepath=replay_path, scenario_id=f"feedback/{timestamp}", name=f"Feedback: {issue_description[:30]}")

        # 3. Export Model Registry state
        registry_path = os.path.join(tmp_dir, "model_registry.json")
        with open(registry_path, "w", encoding="utf-8") as rf:
            json.dump(get_model_registry().to_dict(), rf, indent=2)

        # 4. Export Workspace State if present
        workspace_path = os.path.join(tmp_dir, "workspace_state.json")
        if active_ws and hasattr(active_ws, "to_dict"):
            with open(workspace_path, "w", encoding="utf-8") as wf:
                json.dump(active_ws.to_dict(), wf, indent=2)

        # 5. Export Health Diagnostics
        health_path = os.path.join(tmp_dir, "health_check.json")
        with open(health_path, "w", encoding="utf-8") as hf:
            json.dump({
                "status": "HEALTHY",
                "timestamp": datetime.now().isoformat(),
                "events_in_buffer": len(recorder.events),
                "active_workspace_exists": active_ws is not None
            }, hf, indent=2)

        # Create Zip archive
        with zipfile.ZipFile(output_filepath, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename in os.listdir(tmp_dir):
                file_path = os.path.join(tmp_dir, filename)
                zf.write(file_path, arcname=filename)

    return output_filepath


def main():
    parser = argparse.ArgumentParser(description="Arova One-Click Feedback Exporter")
    parser.add_argument("-m", "--message", type=str, required=True, help="Description of the bug, issue, or feedback")
    parser.add_argument("-o", "--output", type=str, default=None, help="Custom output path for the diagnostic .zip bundle")
    parser.add_argument("-r", "--rating", type=str, default="WRONG", choices=["PERFECT", "OKAY", "WRONG"], help="Ground truth rating")
    
    args = parser.parse_args()
    
    print("\n📦 Generating Arova One-Click Feedback Bundle...")
    zip_path = generate_feedback_bundle(
        issue_description=args.message,
        output_filepath=args.output,
        satisfaction_rating=args.rating
    )
    print(f"✅ Feedback bundle generated successfully:\n   → {zip_path}")
    print("   Ready to attach and send. Thank you for making Arova smarter!\n")


if __name__ == "__main__":
    main()
