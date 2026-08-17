#!/usr/bin/env python3
"""
Arova File Watcher
==================
Watches the current project directory for file saves and captures
structured diff events to the session log.

Design constraints:
- Uses inotify on Linux (via watchfiles), polling fallback on other platforms
- Only watches files in git-tracked directories
- Captures raw unified diffs, truncated at 500 characters
- Writes file_edit events to ~/.local/share/arova/session_log.jsonl
- CPU usage when idle: effectively zero (kernel-driven events)
- Does not index, does not search, does not summarize at capture time

Usage:
    python3 file_watcher.py --project-root /home/sarthak/arova

Stops with Ctrl+C or when the parent process exits.
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOG_FILE = Path.home() / ".local" / "share" / "arova" / "session_log.jsonl"

# File extensions worth watching for code projects
WATCHED_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".rs", ".go", ".java", ".cpp", ".c", ".h",
    ".rb", ".php", ".swift", ".kt",
    ".css", ".scss", ".html",
    ".yaml", ".yml", ".toml", ".json",
    ".md", ".txt", ".env",
    ".sh", ".bash", ".zsh",
    "Makefile", "Dockerfile",
}

# Directories to never watch
IGNORED_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "target", ".next", ".nuxt",
    ".tox", "htmlcov", ".eggs", "*.egg-info",
}

# Maximum raw diff characters to store per event
# Keeps session log manageable. Reconstruction gets the key signal.
MAX_DIFF_CHARS = 500

# Debounce: ignore saves within this many seconds of the previous save
# of the same file. Editors often write multiple times per save.
DEBOUNCE_SECONDS = 1.5

# Minimum file size change to bother diffing (bytes)
# Catches accidental touches without content changes
MIN_CHANGE_BYTES = 1


# ---------------------------------------------------------------------------
# Event writer
# ---------------------------------------------------------------------------

class EventWriter:
    def __init__(self, log_file: Path):
        self._log_file = log_file
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event_type: str, data: dict):
        timestamp = datetime.now(timezone.utc).astimezone().isoformat()
        event = {
            "timestamp": timestamp,
            "type": event_type,
            "data": data,
        }
        with open(self._log_file, "a") as f:
            f.write(json.dumps(event) + "\n")


# ---------------------------------------------------------------------------
# Git interface
# ---------------------------------------------------------------------------

class GitInterface:
    """
    Thin wrapper around git commands.
    All operations are read-only. We never modify the repository.
    """

    def __init__(self, repo_root: str):
        self._root = repo_root

    def is_tracked(self, file_path: str) -> bool:
        """Check if a file is tracked by git (or at least in the repo)."""
        try:
            result = subprocess.run(
                ["git", "ls-files", "--error-unmatch", file_path],
                cwd=self._root,
                capture_output=True,
                timeout=2,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_diff(self, file_path: str) -> str | None:
        """
        Get the diff of a file against HEAD.
        Returns None if the file has no tracked changes or git fails.
        """
        try:
            # First try: diff against HEAD (tracked file, modified)
            result = subprocess.run(
                ["git", "diff", "HEAD", "--", file_path],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout

            # Second try: diff for new untracked files
            result = subprocess.run(
                ["git", "diff", "--cached", "--", file_path],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout

            return None

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def get_repo_root(self) -> str | None:
        """Find the git repo root from the current directory."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=self._root,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None


# ---------------------------------------------------------------------------
# Diff summarizer
# ---------------------------------------------------------------------------

class DiffSummarizer:
    """
    Produces a compact, human-readable summary of a unified diff.
    
    This runs locally without an LLM. The goal is to extract the 
    most semantically significant change in plain English.
    
    For the experiment phase, we store truncated raw diffs. The daily
    reconstruction script handles full summarization via LLM.
    This class provides a lightweight fallback summary.
    """

    def summarize(self, diff: str, file_path: str) -> str:
        """
        Extract a compact summary from a unified diff.
        Returns a single sentence describing the change.
        """
        lines = diff.splitlines()

        added = [l[1:].strip() for l in lines if l.startswith("+") and not l.startswith("+++")]
        removed = [l[1:].strip() for l in lines if l.startswith("-") and not l.startswith("---")]

        # Filter out blank lines and comments
        added = [l for l in added if l and not l.startswith("#")]
        removed = [l for l in removed if l and not l.startswith("#")]

        filename = Path(file_path).name

        if not added and not removed:
            return f"Whitespace or formatting change in {filename}"

        if added and not removed:
            # Pure addition
            if len(added) == 1:
                return f"Added to {filename}: {added[0][:80]}"
            return f"Added {len(added)} lines to {filename}"

        if removed and not added:
            # Pure deletion
            if len(removed) == 1:
                return f"Removed from {filename}: {removed[0][:80]}"
            return f"Removed {len(removed)} lines from {filename}"

        # Mixed changes — try to describe the most significant line
        # Heuristic: the longest added line is usually the most semantic
        most_significant = max(added, key=len) if added else ""

        if len(added) == 1 and len(removed) == 1:
            return f"Changed in {filename}: {removed[0][:40]} → {added[0][:40]}"

        return (
            f"Modified {filename}: {len(added)} additions, {len(removed)} removals. "
            f"Key change: {most_significant[:60]}"
        )

    def truncate_diff(self, diff: str) -> str:
        """
        Truncate diff to MAX_DIFF_CHARS while preserving the most
        informative lines (the actual changes, not the context).
        """
        if len(diff) <= MAX_DIFF_CHARS:
            return diff

        lines = diff.splitlines()

        # Prioritize: header lines and changed lines over context lines
        priority_lines = []
        context_lines = []

        for line in lines:
            if line.startswith(("+", "-", "@@", "diff", "---", "+++")):
                priority_lines.append(line)
            else:
                context_lines.append(line)

        # Build truncated diff from priority lines first
        result = "\n".join(priority_lines)
        if len(result) <= MAX_DIFF_CHARS:
            return result

        # If still too long, truncate with a note
        return result[:MAX_DIFF_CHARS - 20] + "\n... [truncated]"


# ---------------------------------------------------------------------------
# File state tracker (debouncing)
# ---------------------------------------------------------------------------

class FileStateTracker:
    """
    Tracks last-seen modification time per file for debouncing.
    Prevents duplicate events when editors write multiple times per save.
    """

    def __init__(self):
        self._last_event: dict[str, float] = {}
        self._last_size: dict[str, int] = {}

    def should_process(self, file_path: str) -> bool:
        now = time.monotonic()
        last = self._last_event.get(file_path, 0)

        if now - last < DEBOUNCE_SECONDS:
            return False

        # Check if file size actually changed
        try:
            current_size = Path(file_path).stat().st_size
            last_size = self._last_size.get(file_path, -1)

            if last_size != -1 and abs(current_size - last_size) < MIN_CHANGE_BYTES:
                return False

            self._last_size[file_path] = current_size
        except OSError:
            return False

        self._last_event[file_path] = now
        return True

    def record(self, file_path: str):
        self._last_event[file_path] = time.monotonic()


# ---------------------------------------------------------------------------
# Core watcher
# ---------------------------------------------------------------------------

class FileWatcher:
    """
    Main watcher. Uses watchfiles on Linux (inotify-backed) with a
    simple polling fallback.
    """

    def __init__(
        self,
        project_root: str,
        event_writer: EventWriter,
        git: GitInterface,
        summarizer: DiffSummarizer,
        tracker: FileStateTracker,
    ):
        self._root = Path(project_root).resolve()
        self._writer = event_writer
        self._git = git
        self._summarizer = summarizer
        self._tracker = tracker
        self._logger = logging.getLogger(__name__)

    def _should_watch(self, file_path: Path) -> bool:
        """Determine if a file change is worth processing."""
        # Check ignored directories
        for part in file_path.parts:
            if part in IGNORED_DIRS:
                return False

        # Check extension
        suffix = file_path.suffix.lower()
        name = file_path.name

        if suffix in WATCHED_EXTENSIONS:
            return True
        if name in WATCHED_EXTENSIONS:  # Makefile, Dockerfile etc
            return True

        return False

    async def _process_change(self, file_path: str):
        """Handle a detected file change."""
        path = Path(file_path)

        if not self._should_watch(path):
            return

        if not self._tracker.should_process(file_path):
            return

        if not path.exists():
            # File was deleted — record that
            self._writer.write("file_delete", {
                "path": file_path,
                "relative_path": str(path.relative_to(self._root)),
            })
            return

        # Get diff from git
        diff = self._git.get_diff(file_path)

        if diff is None:
            # File changed but no git diff — new untracked file or
            # file matches HEAD exactly. Record minimal event.
            self._writer.write("file_open", {
                "path": file_path,
                "relative_path": str(path.relative_to(self._root)),
                "note": "modified but no git diff available",
            })
            return

        # Produce summary and truncated diff
        summary = self._summarizer.summarize(diff, file_path)
        truncated = self._summarizer.truncate_diff(diff)
        relative = str(path.relative_to(self._root))

        added_count = len([l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")])
        removed_count = len([l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")])

        self._writer.write("file_edit", {
            "path": file_path,
            "relative_path": relative,
            "diff_summary": summary,
            "diff_raw": truncated,
            "lines_added": added_count,
            "lines_removed": removed_count,
        })

        self._logger.info(f"Captured: {relative} - {summary}")

    async def watch_with_watchfiles(self):
        """
        Primary watch method using watchfiles (inotify on Linux).
        Requires: pip install watchfiles
        """
        try:
            from watchfiles import awatch, Change
        except ImportError:
            self._logger.warning(
                "watchfiles not installed. Falling back to polling. "
                "Install with: pip install watchfiles"
            )
            await self.watch_with_polling()
            return

        self._logger.info(f"Watching {self._root} with inotify...")
        self._writer.write("watcher_start", {
            "project_root": str(self._root),
            "method": "inotify",
        })

        async for changes in awatch(str(self._root)):
            for change_type, file_path in changes:
                # We care about modifications and new files
                # Deletions handled in _process_change
                if change_type in (Change.modified, Change.added):
                    await self._process_change(file_path)

    async def watch_with_polling(self, interval_seconds: float = 2.0):
        """
        Fallback polling watcher for non-Linux or when watchfiles unavailable.
        Polls every interval_seconds for mtime changes.
        """
        self._logger.info(f"Watching {self._root} with polling ({interval_seconds}s)...")
        self._writer.write("watcher_start", {
            "project_root": str(self._root),
            "method": "polling",
            "interval_seconds": interval_seconds,
        })

        known_mtimes: dict[str, float] = {}

        while True:
            try:
                for path in self._root.rglob("*"):
                    if not path.is_file():
                        continue
                    if not self._should_watch(path):
                        continue

                    try:
                        mtime = path.stat().st_mtime
                    except OSError:
                        continue

                    path_str = str(path)
                    if path_str in known_mtimes and known_mtimes[path_str] != mtime:
                        await self._process_change(path_str)

                    known_mtimes[path_str] = mtime

            except Exception as e:
                self._logger.warning(f"Polling error: {e}")

            await asyncio.sleep(interval_seconds)

    async def run(self):
        """Entry point. Tries inotify first, falls back to polling."""
        try:
            await self.watch_with_watchfiles()
        except Exception as e:
            self._logger.error(f"inotify watcher failed: {e}. Falling back to polling.")
            await self.watch_with_polling()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def find_project_root(start_path: str) -> str:
    """
    Walk up from start_path to find the git repo root.
    Falls back to start_path if no git repo found.
    """
    path = Path(start_path).resolve()

    for candidate in [path, *path.parents]:
        if (candidate / ".git").exists():
            return str(candidate)

    return str(path)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [file_watcher] %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Arova File Watcher — captures file edit events to session log"
    )
    parser.add_argument(
        "--project-root",
        default=os.getcwd(),
        help="Project root to watch. Defaults to current directory.",
    )
    parser.add_argument(
        "--log-file",
        default=str(LOG_FILE),
        help=f"Session log JSONL file. Defaults to {LOG_FILE}",
    )
    parser.add_argument(
        "--polling",
        action="store_true",
        help="Force polling mode instead of inotify",
    )
    args = parser.parse_args()

    project_root = find_project_root(args.project_root)
    logging.info(f"Project root: {project_root}")

    git = GitInterface(project_root)
    actual_root = git.get_repo_root() or project_root
    logging.info(f"Git repo root: {actual_root}")

    writer = EventWriter(Path(args.log_file))
    summarizer = DiffSummarizer()
    tracker = FileStateTracker()

    watcher = FileWatcher(
        project_root=actual_root,
        event_writer=writer,
        git=git,
        summarizer=summarizer,
        tracker=tracker,
    )

    async def run():
        if args.polling:
            await watcher.watch_with_polling()
        else:
            await watcher.run()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logging.info("File watcher stopped.")
        writer.write("watcher_stop", {"project_root": actual_root})


if __name__ == "__main__":
    main()
