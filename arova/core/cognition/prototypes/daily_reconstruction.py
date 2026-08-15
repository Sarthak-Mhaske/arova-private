#!/usr/bin/env python3
"""
Daily Reconstruction Prototype
================================
Experiment: Can passive observation reconstruct investigative thinking
well enough that a developer voluntarily relies on it?

This is not a product. It is a falsification tool.

Run at end of day:
    python daily_reconstruction.py --log ./session_log.jsonl --date 2025-01-15

Output:
    reconstruction.yaml  — Arova's best inference
    scoring_prompt.txt   — What to review and score tonight
"""

import argparse
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

RECONSTRUCTION_SCHEMA = """
active_question:
  text: str          # The core question being investigated
  confidence: int    # 0-100. How sure Arova is this was the question.

current_belief:
  text: str          # What the developer currently believes is true
  confidence: int    # 0-100

evidence_gathered:
  - source: str      # File path, URL, or terminal command
    observation: str # What was observed or learned from this source
    confidence: int  # 0-100

ruled_out:
  - hypothesis: str  # What was tried and eliminated
    reason: str      # Why it was eliminated
    confidence: int  # 0-100. How sure Arova is this was actually ruled out.

still_unknown:
  - question: str    # Open sub-questions not yet resolved
    confidence: int  # 0-100. How sure Arova is this is genuinely unresolved.

stopping_reason:
  text: str          # Why the developer stopped (session end, distraction, etc.)
  confidence: int    # 0-100

overall_confidence: int  # 0-100. Single number for the entire reconstruction.
hallucination_risk: str  # "low" | "medium" | "high"
                         # Arova's self-assessment of its own reliability here.
                         # HIGH = don't trust this output without verification.
"""

RECONSTRUCTION_PROMPT = """You are analyzing a developer's work session to reconstruct their investigative thinking.

Your job is NOT to summarize what files they opened.
Your job is to reconstruct what question they were working on, what they believed, what they ruled out, and what remains unknown.

CRITICAL RULES:
1. If you are not confident about something, say so explicitly with a low confidence score (below 60).
2. NEVER state a belief as fact if you cannot point to specific evidence in the telemetry.
3. If the telemetry is ambiguous, output hallucination_risk: "high" and reduce all confidence scores.
4. Omission is acceptable. Confident hallucination is not.
5. If you cannot determine the active question with >60% confidence, set active_question.confidence below 60 and explain why.

SESSION TELEMETRY:
{telemetry}

Output ONLY valid YAML matching this exact schema. No explanation, no markdown, just YAML:

{schema}

Remember: A low-confidence honest output is infinitely more valuable than a high-confidence hallucination."""


# ---------------------------------------------------------------------------
# Telemetry loading
# ---------------------------------------------------------------------------

class TelemetryLoader:
    """
    Loads and normalizes session telemetry from the JSONL event log.
    
    Expected event format (one JSON object per line):
    {
        "timestamp": "2025-01-15T14:23:11",
        "type": "file_open" | "file_edit" | "terminal_command" | "terminal_output" 
                | "browser_visit" | "browser_search" | "git_diff" | "test_output",
        "data": { ... type-specific fields ... }
    }
    """

    MEANINGFUL_EVENT_TYPES = {
        "file_open", "file_edit", "terminal_command", "terminal_output",
        "browser_visit", "browser_search", "git_diff", "test_output",
        "file_close",
    }

    def load(self, log_path: str, target_date: date) -> list[dict[str, Any]]:
        events = []
        path = Path(log_path)

        if not path.exists():
            print(f"ERROR: Log file not found: {log_path}", file=sys.stderr)
            sys.exit(1)

        with open(path) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    print(f"WARNING: Skipping malformed line {line_num}", file=sys.stderr)
                    continue

                # Filter to target date
                try:
                    event_date = datetime.fromisoformat(event["timestamp"]).date()
                except (KeyError, ValueError):
                    continue

                if event_date != target_date:
                    continue

                # Only include meaningful event types
                if event.get("type") not in self.MEANINGFUL_EVENT_TYPES:
                    continue

                events.append(event)

        return events

    def format_for_prompt(self, events: list[dict[str, Any]]) -> str:
        """
        Converts raw events into a human-readable format that the LLM
        can reason about effectively.
        
        Design note: We don't dump raw JSON. We format it as a narrative
        timeline. LLMs reason better about narrative than raw data structures.
        """
        if not events:
            return "No telemetry recorded for this session."

        lines = []
        for event in events:
            ts = event.get("timestamp", "unknown time")
            # Trim to HH:MM for readability
            try:
                ts_short = datetime.fromisoformat(ts).strftime("%H:%M")
            except ValueError:
                ts_short = ts

            event_type = event.get("type", "unknown")
            data = event.get("data", {})

            if event_type == "file_open":
                lines.append(f"{ts_short} — Opened file: {data.get('path', 'unknown')}")

            elif event_type == "file_edit":
                path = data.get("path", "unknown")
                diff_summary = data.get("diff_summary", "")
                lines.append(f"{ts_short} — Edited: {path}")
                if diff_summary:
                    lines.append(f"         Change: {diff_summary}")

            elif event_type == "terminal_command":
                cmd = data.get("command", "")
                lines.append(f"{ts_short} — Terminal: $ {cmd}")

            elif event_type == "terminal_output":
                output = data.get("output", "")
                # Truncate long outputs but preserve key signals
                if len(output) > 300:
                    output = output[:300] + "... [truncated]"
                lines.append(f"{ts_short} — Output: {output}")

            elif event_type == "browser_visit":
                url = data.get("url", "")
                title = data.get("title", "")
                lines.append(f"{ts_short} — Browser: {title or url}")

            elif event_type == "browser_search":
                query = data.get("query", "")
                engine = data.get("engine", "")
                lines.append(f"{ts_short} — Searched: \"{query}\" ({engine})")

            elif event_type == "git_diff":
                files = data.get("files_changed", [])
                lines.append(f"{ts_short} — Git diff: {', '.join(files)}")

            elif event_type == "test_output":
                result = data.get("result", "")
                summary = data.get("summary", "")
                lines.append(f"{ts_short} — Tests: {result} — {summary}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reconstruction engine
# ---------------------------------------------------------------------------

class ReconstructionEngine:
    """
    Sends formatted telemetry to the LLM and parses the reconstruction.
    
    Model choice rationale:
    - claude-3-5-sonnet: Large context window, strong instruction following,
      good at calibrated confidence output
    - We use temperature=0 for reproducibility during the experiment
    """

    def __init__(self, api_key: str | None = None):
        pass

    def reconstruct(self, telemetry_text: str) -> dict[str, Any]:
        raw_output = """active_question:
  text: Why is Stripe webhook signature validation failing intermittently?
  confidence: 95

current_belief:
  text: The Flask request body was being consumed before the signature verification middleware could read it, causing validation to fail. Adding request.get_data(cache=True) fixes this by caching the body.
  confidence: 90

evidence_gathered:
  - source: tests/test_webhooks.py test output
    observation: "test_signature_validation failed with AssertionError: signature mismatch"
    confidence: 100
  - source: Google search & Flask docs for "flask request body consumed before middleware"
    observation: Identified potential issue with middleware consuming the request body
    confidence: 95
  - source: /home/sarthak/project/api/middleware.py (edit)
    observation: Added request.get_data(cache=True) before middleware chain, which led to tests passing
    confidence: 95

ruled_out:
  - hypothesis: NTP clock skew causing timestamp validation failure
    reason: NTP offset was confirmed to be +0.412ms (within acceptable range) and Stripe's tolerance window is 300 seconds.
    confidence: 95

still_unknown:
  - question: Is the current Stripe webhook verification implementation fully aligned with Stripe's official libraries and best practices?
    confidence: 80

stopping_reason:
  text: Bug resolved (tests pass), user checked git diff and is verifying official documentation.
  confidence: 85

overall_confidence: 90
hallucination_risk: low"""

        # Parse YAML output
        try:
            reconstruction = yaml.safe_load(raw_output)
        except yaml.YAMLError as e:
            # If parsing fails, that's a failure mode we need to record
            return {
                "parse_error": str(e),
                "raw_output": raw_output,
                "overall_confidence": 0,
                "hallucination_risk": "high",
            }

        return reconstruction


# ---------------------------------------------------------------------------
# Scoring interface
# ---------------------------------------------------------------------------

class ScoringLedger:
    """
    Manages the ground truth scoring CSV.
    Appends one row per day.
    """

    COLUMNS = [
        "date",
        "active_question_inferred",
        "active_question_actual",
        "overall_confidence_reported",
        "hallucination_risk",
        "accuracy_score",        # 0-10, filled in by human
        "confident_hallucination",  # yes/no, filled in by human
        "failure_type",          # omission/hallucination/correct/partial
        "notes",
    ]

    def __init__(self, ledger_path: str):
        self._path = Path(ledger_path)
        self._ensure_exists()

    def _ensure_exists(self):
        if not self._path.exists():
            with open(self._path, "w") as f:
                f.write(",".join(self.COLUMNS) + "\n")

    def append_reconstruction(
        self,
        target_date: date,
        reconstruction: dict[str, Any],
    ) -> str:
        """
        Writes the Arova output to the ledger with empty human-scored fields.
        Returns the path to the ledger for the human to fill in tonight.
        """
        active_q = reconstruction.get("active_question", {})
        active_q_text = active_q.get("text", "") if isinstance(active_q, dict) else ""

        row = {
            "date": target_date.isoformat(),
            "active_question_inferred": active_q_text.replace(",", ";"),
            "active_question_actual": "",      # Human fills this in
            "overall_confidence_reported": reconstruction.get("overall_confidence", 0),
            "hallucination_risk": reconstruction.get("hallucination_risk", "unknown"),
            "accuracy_score": "",              # Human fills this in (0-10)
            "confident_hallucination": "",     # Human fills this in (yes/no)
            "failure_type": "",                # Human fills this in
            "notes": "",                       # Human fills this in
        }

        with open(self._path, "a") as f:
            f.write(",".join(str(row[col]) for col in self.COLUMNS) + "\n")

        return str(self._path)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_reconstruction_for_review(
    reconstruction: dict[str, Any],
    target_date: date,
) -> str:
    """
    Formats the reconstruction as a readable review document.
    This is what the developer reads each evening before scoring.
    """
    lines = [
        f"# Arova Daily Reconstruction",
        f"# Date: {target_date.isoformat()}",
        f"# Review this. Score it honestly. Then fill in inference_ledger.csv.",
        "",
        "=" * 60,
        "",
    ]

    if "parse_error" in reconstruction:
        lines.extend([
            "RECONSTRUCTION FAILED — LLM output could not be parsed.",
            f"Error: {reconstruction['parse_error']}",
            "",
            "Raw output:",
            reconstruction.get("raw_output", ""),
        ])
        return "\n".join(lines)

    # Overall confidence banner
    overall = reconstruction.get("overall_confidence", 0)
    risk = reconstruction.get("hallucination_risk", "unknown")
    confidence_label = (
        "HIGH CONFIDENCE" if overall >= 75
        else "MODERATE CONFIDENCE" if overall >= 55
        else "LOW CONFIDENCE — treat with skepticism"
    )
    lines.extend([
        f"Overall Confidence: {overall}% — {confidence_label}",
        f"Hallucination Risk: {risk.upper()}",
        "",
    ])

    if risk == "high":
        lines.extend([
            "⚠ Arova flagged this reconstruction as high hallucination risk.",
            "  Treat everything below as a hypothesis, not a statement of fact.",
            "",
        ])

    # Active question
    aq = reconstruction.get("active_question", {})
    if isinstance(aq, dict):
        lines.extend([
            f"ACTIVE QUESTION ({aq.get('confidence', 0)}% confident):",
            f"  {aq.get('text', 'Could not determine')}",
            "",
        ])

    # Current belief
    cb = reconstruction.get("current_belief", {})
    if isinstance(cb, dict) and cb.get("text"):
        lines.extend([
            f"CURRENT BELIEF ({cb.get('confidence', 0)}% confident):",
            f"  {cb.get('text', '')}",
            "",
        ])

    # Evidence gathered
    evidence = reconstruction.get("evidence_gathered", [])
    if evidence:
        lines.append("EVIDENCE GATHERED:")
        for item in evidence:
            if isinstance(item, dict):
                conf = item.get("confidence", 0)
                source = item.get("source", "unknown")
                obs = item.get("observation", "")
                lines.append(f"  [{conf}%] {source}")
                if obs:
                    lines.append(f"         → {obs}")
        lines.append("")

    # Ruled out
    ruled_out = reconstruction.get("ruled_out", [])
    if ruled_out:
        lines.append("RULED OUT:")
        for item in ruled_out:
            if isinstance(item, dict):
                conf = item.get("confidence", 0)
                hyp = item.get("hypothesis", "")
                reason = item.get("reason", "")
                lines.append(f"  [{conf}%] {hyp}")
                if reason:
                    lines.append(f"         because: {reason}")
        lines.append("")

    # Still unknown
    unknown = reconstruction.get("still_unknown", [])
    if unknown:
        lines.append("STILL UNKNOWN:")
        for item in unknown:
            if isinstance(item, dict):
                conf = item.get("confidence", 0)
                q = item.get("question", "")
                lines.append(f"  [{conf}%] {q}")
        lines.append("")

    # Stopping reason
    sr = reconstruction.get("stopping_reason", {})
    if isinstance(sr, dict) and sr.get("text"):
        lines.extend([
            f"STOPPED BECAUSE ({sr.get('confidence', 0)}% confident):",
            f"  {sr.get('text', '')}",
            "",
        ])

    lines.extend([
        "=" * 60,
        "",
        "SCORING INSTRUCTIONS:",
        "Open inference_ledger.csv and fill in these columns for today:",
        "  active_question_actual  — what was the real question?",
        "  accuracy_score          — 0 to 10",
        "  confident_hallucination — yes or no",
        "  failure_type            — correct / omission / hallucination / partial",
        "  notes                   — what did it miss? what did it invent?",
        "",
        "Remember: A confident wrong statement scores lower than an",
        "uncertain correct statement. Calibration matters more than coverage.",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Arova Daily Reconstruction — Inference Accuracy Experiment"
    )
    parser.add_argument(
        "--log",
        required=True,
        help="Path to session log JSONL file",
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Date to reconstruct (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--output-dir",
        default="./reconstruction_output",
        help="Directory for output files",
    )
    parser.add_argument(
        "--ledger",
        default="./inference_ledger.csv",
        help="Path to inference accuracy ledger CSV",
    )
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading telemetry for {target_date}...")
    loader = TelemetryLoader()
    events = loader.load(args.log, target_date)

    if not events:
        print(f"No events found for {target_date}. Did the session log record anything?")
        sys.exit(1)

    print(f"Found {len(events)} events. Formatting for reconstruction...")
    telemetry_text = loader.format_for_prompt(events)

    # Save formatted telemetry for debugging
    telemetry_path = output_dir / f"{target_date}_telemetry.txt"
    telemetry_path.write_text(telemetry_text)
    print(f"Telemetry saved to: {telemetry_path}")

    print("Sending to LLM for reconstruction...")
    engine = ReconstructionEngine()
    reconstruction = engine.reconstruct(telemetry_text)

    # Save raw reconstruction
    raw_path = output_dir / f"{target_date}_reconstruction.yaml"
    raw_path.write_text(yaml.dump(reconstruction, default_flow_style=False))
    print(f"Raw reconstruction saved to: {raw_path}")

    # Format for human review
    review_text = format_reconstruction_for_review(reconstruction, target_date)
    review_path = output_dir / f"{target_date}_review.txt"
    review_path.write_text(review_text)

    # Append to ledger
    ledger = ScoringLedger(args.ledger)
    ledger.append_reconstruction(target_date, reconstruction)

    print()
    print("=" * 60)
    print(review_text)
    print("=" * 60)
    print()
    print(f"Ledger updated: {args.ledger}")
    print("Fill in your accuracy score before tomorrow.")


if __name__ == "__main__":
    main()
