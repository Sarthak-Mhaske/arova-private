# Migration to Arova

The legacy `HyprVoice` repository is frozen. Arova is a completely new architecture.

## Principles of Migration
- **Zero UI in Core**: `arova.core` must never import GTK, GLib, or UI dependencies.
- **Strict Subprocesses**: Direct calls to `subprocess.run` are forbidden in capabilities. All execution must go through the `SystemExecutionLayer`.
- **Platform Agnosticism**: Hardcoded OS windowing (like Hyprland) must be abstracted via the `WindowingBackend`.
