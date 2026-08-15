#!/usr/bin/env python3
"""
Arova Shell Hook Installer
===========================
Safely installs the shell hook into the user's shell configuration.

Design principles:
- Never overwrites existing shell config
- Idempotent: running twice has no additional effect  
- Easy to uninstall: leaves a clear comment marker
- Supports zsh and bash
- Verifies hook file exists before modifying shell config
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


# The marker we use to find our block in shell config files
AROVA_BLOCK_START = "# >>> arova shell hook >>>"
AROVA_BLOCK_END = "# <<< arova shell hook <<<"


def get_hook_source_path() -> Path:
    """Find shell_hook.sh relative to this script."""
    this_dir = Path(__file__).parent
    hook_path = this_dir / "shell_hook.sh"
    if not hook_path.exists():
        print(f"ERROR: shell_hook.sh not found at {hook_path}", file=sys.stderr)
        print("Make sure you're running install_hooks.py from the correct directory.")
        sys.exit(1)
    return hook_path


def get_install_path() -> Path:
    """Where to install the hook script."""
    arova_dir = Path.home() / ".arova"
    arova_dir.mkdir(parents=True, exist_ok=True)
    return arova_dir / "shell_hook.sh"


def detect_shell() -> str:
    """Detect the user's current shell."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return "zsh"
    elif "bash" in shell:
        return "bash"
    else:
        return "unknown"


def get_rc_files(shell: str) -> list[Path]:
    """Return the shell config files to modify, in priority order."""
    home = Path.home()
    if shell == "zsh":
        return [home / ".zshrc"]
    elif shell == "bash":
        # Bash reads .bashrc for interactive non-login shells
        # and .bash_profile / .profile for login shells
        # We install into .bashrc and .bash_profile both
        candidates = [home / ".bashrc", home / ".bash_profile"]
        return [p for p in candidates if p.exists()] or [home / ".bashrc"]
    else:
        # Unknown shell: try common options
        return [p for p in [home / ".zshrc", home / ".bashrc"] if p.exists()]


def is_hook_already_installed(rc_file: Path) -> bool:
    """Check if our hook block already exists in the rc file."""
    if not rc_file.exists():
        return False
    content = rc_file.read_text(errors="replace")
    return AROVA_BLOCK_START in content


def backup_rc_file(rc_file: Path) -> Path:
    """Create a timestamped backup before modifying."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = rc_file.parent / f"{rc_file.name}.arova_backup_{timestamp}"
    shutil.copy2(rc_file, backup_path)
    return backup_path


def install_hook_into_rc(rc_file: Path, hook_install_path: Path) -> bool:
    """
    Appends the source block to the rc file.
    Returns True if installed, False if already present.
    """
    if is_hook_already_installed(rc_file):
        print(f"  Already installed in {rc_file}")
        return False

    # Create rc file if it doesn't exist
    if not rc_file.exists():
        rc_file.touch()
        print(f"  Created {rc_file}")
    else:
        backup = backup_rc_file(rc_file)
        print(f"  Backed up to {backup}")

    hook_block = f"""
{AROVA_BLOCK_START}
# Arova shell telemetry hook.
# This captures structured terminal events for work context intelligence.
# To remove: delete the lines between the arova markers.
[ -f "{hook_install_path}" ] && source "{hook_install_path}"
{AROVA_BLOCK_END}
"""

    with open(rc_file, "a") as f:
        f.write(hook_block)

    print(f"  Installed into {rc_file}")
    return True


def remove_hook_from_rc(rc_file: Path) -> bool:
    """
    Removes our hook block from the rc file.
    Returns True if removed, False if not present.
    """
    if not rc_file.exists() or not is_hook_already_installed(rc_file):
        return False

    content = rc_file.read_text(errors="replace")
    lines = content.splitlines(keepends=True)

    new_lines = []
    inside_block = False

    for line in lines:
        if AROVA_BLOCK_START in line:
            inside_block = True
            continue
        if AROVA_BLOCK_END in line:
            inside_block = False
            continue
        if not inside_block:
            new_lines.append(line)

    backup = backup_rc_file(rc_file)
    print(f"  Backed up to {backup}")

    rc_file.write_text("".join(new_lines))
    print(f"  Removed from {rc_file}")
    return True


def verify_installation(hook_install_path: Path) -> dict[str, bool]:
    """
    Runs basic verification of the installed hook.
    Returns a dict of check_name -> passed.
    """
    checks = {}

    # Check 1: Hook file exists and is readable
    checks["hook_file_exists"] = hook_install_path.exists()

    # Check 2: Hook file has no obvious syntax errors
    if checks["hook_file_exists"]:
        result = subprocess.run(
            ["bash", "-n", str(hook_install_path)],
            capture_output=True,
            text=True,
        )
        checks["hook_syntax_valid"] = result.returncode == 0

    # Check 3: Log directory is writable
    log_dir = Path.home() / ".local" / "share" / "arova"
    log_dir.mkdir(parents=True, exist_ok=True)
    test_file = log_dir / ".write_test"
    try:
        test_file.touch()
        test_file.unlink()
        checks["log_dir_writable"] = True
    except OSError:
        checks["log_dir_writable"] = False

    # Check 4: JSON logging works (source hook in subprocess and run a test)
    if checks.get("hook_syntax_valid"):
        log_file = log_dir / "session_log.jsonl"
        initial_size = log_file.stat().st_size if log_file.exists() else 0

        test_script = f"""
source {hook_install_path}
_arova_preexec "pytest tests/ -v"
"""
        result = subprocess.run(
            ["bash", test_script],
            capture_output=True,
            text=True,
        )

        # Give it a moment to write
        import time
        time.sleep(0.2)

        new_size = log_file.stat().st_size if log_file.exists() else 0
        checks["test_event_written"] = new_size > initial_size

    return checks


def print_next_steps(shell: str, rc_files: list[Path]):
    """Print clear instructions for what the user needs to do next."""
    print()
    print("=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print()
    print("1. Reload your shell configuration:")
    for rc in rc_files:
        if rc.exists():
            print(f"   source {rc}")
    print()
    print("2. Verify the hook is active:")
    print("   Run a few commands, then check:")
    print("   tail -5 ~/.local/share/arova/session_log.jsonl")
    print()
    print("3. You should see structured JSON events like:")
    print('   {"timestamp":"...","type":"terminal_command","data":{...}}')
    print()
    print("To uninstall at any time:")
    print("   python3 install_hooks.py --uninstall")
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Install or remove the Arova shell telemetry hook"
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove the hook from shell config files",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify the installation, don't modify anything",
    )
    args = parser.parse_args()

    print()
    print("Arova Shell Hook Installer")
    print("-" * 40)

    shell = detect_shell()
    print(f"Detected shell: {shell}")

    rc_files = get_rc_files(shell)
    print(f"Shell config files: {[str(p) for p in rc_files]}")
    print()

    # --- Uninstall mode ---
    if args.uninstall:
        print("Removing Arova shell hook...")
        any_removed = False
        for rc_file in rc_files:
            if remove_hook_from_rc(rc_file):
                any_removed = True

        hook_install_path = get_install_path()
        if hook_install_path.exists():
            hook_install_path.unlink()
            print(f"Removed hook file: {hook_install_path}")

        if any_removed:
            print()
            print("Uninstalled. Reload your shell to complete removal:")
            for rc in rc_files:
                if rc.exists():
                    print(f"  source {rc}")
        else:
            print("Hook was not installed. Nothing to remove.")
        return

    # --- Verify only mode ---
    hook_install_path = get_install_path()
    if args.verify_only:
        print("Verifying installation...")
        checks = verify_installation(hook_install_path)
        all_passed = True
        for check, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check}")
            if not passed:
                all_passed = False
        sys.exit(0 if all_passed else 1)

    # --- Install mode ---

    # Copy hook script to user's ~/.arova/
    hook_source = get_hook_source_path()
    shutil.copy2(hook_source, hook_install_path)
    hook_install_path.chmod(0o644)
    print(f"Installed hook script to: {hook_install_path}")
    print()

    # Install into shell rc files
    print("Modifying shell configuration...")
    any_installed = False
    for rc_file in rc_files:
        if install_hook_into_rc(rc_file, hook_install_path):
            any_installed = True

    if not any_installed:
        print()
        print("Hook already installed. Running verification...")
    else:
        print()
        print("Running verification...")

    checks = verify_installation(hook_install_path)
    all_passed = True
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
        if not passed:
            all_passed = False

    if all_passed:
        print()
        print("✓ Installation verified successfully.")
    else:
        print()
        print("⚠ Some checks failed. See above for details.")
        print("  The hook may still work — reload your shell and test manually.")

    print_next_steps(shell, rc_files)


if __name__ == "__main__":
    main()
