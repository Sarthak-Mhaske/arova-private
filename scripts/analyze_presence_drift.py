import argparse
import sys
from arova.core.presence.journal import PresenceJournalSystem
from arova.core.presence.trust_calibration import PresenceResilienceMetrics

def analyze_drift(journal_dir: str):
    system = PresenceJournalSystem(journal_dir=journal_dir)
    reflections = system.read_valid_reflections()
    
    if not reflections:
        print("No valid presence telemetry found. Arova has been entirely silent or no reflections were logged.")
        sys.exit(0)
        
    metrics = PresenceResilienceMetrics(reflections)
    
    print("\n=== Arova Presence Resilience Report ===")
    print(f"Total Logged Reflections: {len(reflections)}")
    
    # Calculate specific metrics
    avg_annoyance = sum(r.annoyance_score for r in reflections) / len(reflections)
    avg_usefulness = sum(r.perceived_usefulness for r in reflections) / len(reflections)
    
    print("\n[Subjective Pacing Metrics]")
    print(f"- Ambient Acceptance Rate: {metrics.ambient_acceptance_rate * 100:.1f}%")
    print(f"- Annoyance Half-Life (Resilience): {metrics.annoyance_half_life * 100:.1f}%")
    print(f"- Average Annoyance Score: {avg_annoyance:.2f}")
    print(f"- Average Perceived Usefulness: {avg_usefulness:.2f}")
    
    print("\n[Drift Analysis]")
    if avg_annoyance > 0.5:
        print("⚠️ WARNING: Presence Fatigue Detected. Arova is currently too active or poorly timed.")
    elif avg_usefulness < 0.2:
        print("⚠️ WARNING: Intelligence Sparsity Failed. Arova is speaking without adding sufficient value.")
    else:
        print("✓ Presence pacing is emotionally sustainable.")
        
    print("\n[Privacy Note]")
    print(f"This telemetry remains strictly local in {system.journal_dir}")

def main():
    parser = argparse.ArgumentParser(description="Analyze Arova's experiential presence telemetry.")
    parser.add_argument("--journal-dir", type=str, default="~/.local/share/arova/journals/",
                        help="Directory containing local presence logs.")
    parser.add_argument("--export", action="store_true", help="Format output for external export (e.g. sharing with developers).")
    
    args = parser.parse_args()
    
    analyze_drift(args.journal_dir)

if __name__ == "__main__":
    main()
