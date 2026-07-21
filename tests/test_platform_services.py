"""
Unit tests for Arova Platform Services (`Phase 7 Platform Services`).
Tests core data structures, application discovery, affinity learning, deep adapters,
restore planning, capability registry dispatch, and Linux launcher fallbacks.
"""
import os
import time
import pytest
from unittest.mock import patch, MagicMock

from arova.core.platform.services.capabilities import Capability, CapabilityRegistry
from arova.core.platform.services.intents import RestoreIntent, LaunchPlan, LaunchResult
from arova.core.platform.services.catalog import ApplicationEntry
from arova.core.platform.services.affinity import ApplicationAffinity
from arova.core.platform.services.adapters import VSCodeAdapter, JetBrainsAdapter, get_adapter
from arova.core.platform.services.backends.linux import LinuxApplicationCatalog, LinuxPlatformLauncher, LinuxBackend
from arova.core.platform.services.backend import PlatformBackend
from arova.core.cognition.restore_planner import RestorePlanner


def test_capability_registry_registration_and_dispatch():
    registry = CapabilityRegistry()
    mock_handler = MagicMock(return_value=LaunchResult(RestoreIntent("source_file", Capability.OPEN_FILE), True, "TestApp", "Success"))

    assert not registry.can_handle(Capability.OPEN_FILE)
    registry.register(Capability.OPEN_FILE, mock_handler)
    assert registry.can_handle(Capability.OPEN_FILE)

    intent = RestoreIntent("source_file", Capability.OPEN_FILE, resource_path="/tmp/test.py")
    result = registry.execute(Capability.OPEN_FILE, intent)

    assert result.success is True
    assert result.application_name == "TestApp"
    mock_handler.assert_called_once_with(intent)

    # Test unregistered capability handling
    unreg_result = registry.execute(Capability.OPEN_URL, RestoreIntent("webpage", Capability.OPEN_URL))
    assert unreg_result.success is False
    assert "Unregistered capability" in str(unreg_result.error)


def test_restore_intent_and_launch_plan_serialization():
    intent = RestoreIntent(
        kind="source_file",
        capability=Capability.OPEN_FILE,
        resource_path="/home/sarthak/arova/main.py",
        preferred_application="code",
        confidence=0.96,
        metadata={"line": 174, "col": 1},
        priority=2
    )

    data = intent.to_dict()
    assert data["kind"] == "source_file"
    assert data["capability"] == "OPEN_FILE"
    assert data["metadata"]["line"] == 174

    restored_intent = RestoreIntent.from_dict(data)
    assert restored_intent.capability == Capability.OPEN_FILE
    assert restored_intent.resource_path == "/home/sarthak/arova/main.py"

    plan = LaunchPlan(
        workspace_id="ws_123",
        workspace_title="My Project",
        intents=[intent],
        approved=False
    )
    summary = plan.summary_for_ui()
    assert len(summary) == 1
    assert summary[0]["action"] == "Open File"
    assert summary[0]["resource"] == "main.py"
    assert summary[0]["application"] == "code"


def test_application_entry_capability_inference():
    # Synthetic desktop file entry simulation
    entry = ApplicationEntry(
        app_id="blender.desktop",
        name="Blender",
        executable="/usr/bin/blender",
        exec_template="blender %f",
        icon="blender",
        mime_types=["application/x-blender"],
        categories=["Graphics", "3DGraphics"],
        capabilities={Capability.OPEN_FILE},
        is_terminal=False
    )
    assert Capability.OPEN_FILE in entry.capabilities
    data = entry.to_dict()
    assert "OPEN_FILE" in data["capabilities"]


def test_application_affinity_learning_and_preferences():
    affinity = ApplicationAffinity()
    assert affinity.get_preferred_app(".py") is None

    # Record usage
    for _ in range(45):
        affinity.record_usage(".py", "code")
    for _ in range(3):
        affinity.record_usage(".py", "cursor")
    for _ in range(2):
        affinity.record_usage(".py", "nvim")

    assert affinity.get_preferred_app(".py") == "code"
    dist = affinity.get_affinity_distribution(".py")
    assert dist["code"] == 0.9
    assert dist["cursor"] == 0.06

    # Test serialization
    data = affinity.to_dict()
    restored_affinity = ApplicationAffinity.from_dict(data)
    assert restored_affinity.get_preferred_app(".py") == "code"


def test_deep_adapters_enhancements():
    # 1. VS Code adapter (--goto target, --reuse-window)
    vscode = VSCodeAdapter()
    assert vscode.can_restore_state() is True
    intent_with_line = RestoreIntent("source_file", Capability.OPEN_FILE, resource_path="/tmp/foo.py", metadata={"line": 42, "col": 10})
    enhanced_args = vscode.enhance_launch_args(["code"], intent_with_line)
    assert "--reuse-window" in enhanced_args
    assert "-g" in enhanced_args
    assert "/tmp/foo.py:42:10" in enhanced_args

    # 2. JetBrains adapter (--line n)
    jb = JetBrainsAdapter()
    enhanced_jb = jb.enhance_launch_args(["idea"], intent_with_line)
    assert "--line" in enhanced_jb
    assert "42" in enhanced_jb
    assert "/tmp/foo.py" in enhanced_jb

    # 3. Registry lookup
    assert isinstance(get_adapter("code"), VSCodeAdapter)
    assert isinstance(get_adapter("idea"), JetBrainsAdapter)


def test_linux_catalog_scanning(tmp_path):
    # Create synthetic .desktop file in a temporary directory
    desktop_file = tmp_path / "test-editor.desktop"
    desktop_file.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Test Editor\n"
        "Exec=test-editor %F\n"
        "Icon=text-editor\n"
        "Categories=TextEditor;IDE;\n"
        "MimeType=text/plain;application/x-python;\n",
        encoding="utf-8"
    )

    catalog = LinuxApplicationCatalog()
    with patch("glob.glob", return_value=[str(desktop_file)]), patch("os.path.isdir", return_value=True), patch("shutil.which", return_value="/usr/bin/test-editor"):
        catalog.scan()
        app = catalog.get_application("test-editor")
        assert app is not None
        assert app.name == "Test Editor"
        assert Capability.OPEN_FILE in app.capabilities
        assert Capability.OPEN_FOLDER in app.capabilities  # inferred from IDE category
        assert app.installed is True

        handler = catalog.find_handler_for_mime("text/plain")
        assert handler == app


@patch("subprocess.Popen")
@patch("shutil.which")
def test_linux_platform_launcher_file_and_terminal(mock_which, mock_popen):
    mock_which.return_value = "/usr/bin/code"
    catalog = MagicMock()
    app_entry = ApplicationEntry(app_id="code.desktop", name="Visual Studio Code", executable="/usr/bin/code", exec_template="code %F")
    catalog.get_application.return_value = app_entry
    catalog.get_default_terminal.return_value = ApplicationEntry(app_id="term.desktop", name="Alacritty", executable="/usr/bin/alacritty", exec_template="alacritty")

    launcher = LinuxPlatformLauncher(catalog)

    # 1. Open existing file
    with patch("os.path.exists", return_value=True):
        res = launcher.open_file("/home/sarthak/test.py", line=10, col=5, app=app_entry)
        assert res.success is True
        assert res.application_name == "Visual Studio Code"
        mock_popen.assert_called()

    # 2. Create terminal
    with patch("os.path.isdir", return_value=True):
        t_res = launcher.create_terminal("/home/sarthak/project", command_hint="git status")
        assert t_res.success is True
        assert "Prepared working directory" in t_res.detail
        assert "git status" in t_res.detail


def test_restore_planner_from_workspace_and_affinity():
    catalog = MagicMock()
    catalog.find_handler_for_file.return_value = ApplicationEntry("nvim.desktop", "Neovim", "nvim", "nvim %f")
    catalog.get_default_browser.return_value = ApplicationEntry("brave.desktop", "Brave", "brave", "brave %u")

    affinity = ApplicationAffinity()
    affinity.record_usage(".py", "code")

    planner = RestorePlanner(catalog, affinity)

    ws = MagicMock()
    ws.workspace_id = "ws_test_planner"
    ws.title = "Planner Test Workspace"
    ws.reality.resources = {
        "/home/sarthak/arova/main.py": {"type": "file", "line": 15},
        "/home/sarthak/arova/README.md": {"type": "file", "line": 1},
        "https://docs.python.org/3/": {"type": "url", "summary": "Python docs"},
    }
    ws.interpretation.repo_paths = ["/home/sarthak/arova"]

    plan = planner.plan(ws, {"restore_vscode": True, "restore_terminal": True, "restore_chrome": True})
    assert isinstance(plan, LaunchPlan)
    assert len(plan.intents) >= 4  # repo, 2 files, terminal derived from repo, 1 url

    # Verify that .py file preferred application was taken from affinity ('code')
    py_intent = next((i for i in plan.intents if i.kind == "source_file" and i.resource_path.endswith(".py")), None)
    assert py_intent is not None
    assert py_intent.preferred_application == "code"

    # Verify that .md file preferred application fell back to catalog handler ('nvim')
    md_intent = next((i for i in plan.intents if i.kind == "source_file" and i.resource_path.endswith(".md")), None)
    assert md_intent is not None
    assert md_intent.preferred_application == "nvim"


def test_platform_backend_factory_and_registration():
    backend = PlatformBackend.create()
    assert isinstance(backend, LinuxBackend)
    assert backend.catalog() is not None
    assert backend.launcher() is not None

    registry = CapabilityRegistry()
    backend.register_capabilities(registry)
    assert registry.can_handle(Capability.OPEN_FILE)
    assert registry.can_handle(Capability.OPEN_URL)
    assert registry.can_handle(Capability.CREATE_TERMINAL)


def test_macos_and_windows_backends_contract():
    from arova.core.platform.services.backends.macos import MacOSBackend
    from arova.core.platform.services.backends.windows import WindowsBackend

    mac = MacOSBackend()
    assert mac.catalog() is not None
    assert mac.launcher() is not None
    assert hasattr(mac, "execute")
    assert hasattr(mac, "process_manager")
    assert hasattr(mac, "file_associations")

    win = WindowsBackend()
    assert win.catalog() is not None
    assert win.launcher() is not None
    assert hasattr(win, "execute")
    assert hasattr(win, "process_manager")
    assert hasattr(win, "file_associations")

    with patch("platform.system", return_value="Darwin"):
        b = PlatformBackend.create()
        assert isinstance(b, MacOSBackend)

    with patch("platform.system", return_value="Windows"):
        b = PlatformBackend.create()
        assert isinstance(b, WindowsBackend)


def test_backend_execute_contract():
    backend = PlatformBackend.create()
    intent = RestoreIntent("webpage", Capability.OPEN_URL, resource_url="https://sqlite.org/docs")
    with patch("webbrowser.open") as mock_open:
        res = backend.execute(intent)
        assert res.success is True
        mock_open.assert_called_once_with("https://sqlite.org/docs")


def test_permissions_and_environment_services():
    from arova.core.platform.services.backends.linux import LinuxBackend
    from arova.core.platform.services.backends.macos import MacOSBackend
    from arova.core.platform.services.backends.windows import WindowsBackend

    for backend_cls in [LinuxBackend, MacOSBackend, WindowsBackend]:
        backend = backend_cls()
        perms = backend.permissions()
        env = backend.environment()
        assert hasattr(perms, "check_screen_capture")
        assert hasattr(perms, "check_accessibility")
        assert hasattr(perms, "check_notifications")
        assert hasattr(env, "is_wsl")
        assert hasattr(env, "is_sandboxed")
        assert hasattr(env, "windowing_system")
        assert hasattr(env, "is_remote_desktop")
        assert isinstance(perms.check_screen_capture(), bool)
        assert isinstance(env.windowing_system(), str)


def test_intent_executor_and_affinity_loop():
    from arova.core.cognition.intent_executor import IntentExecutor
    from arova.core.platform.services.intents import LaunchPlan, RestoreIntent

    backend = PlatformBackend.create()
    affinity = ApplicationAffinity()
    executor = IntentExecutor(max_batch_without_prompt=2)

    # 1. Batch policy check
    plan = LaunchPlan("ws_batch", "Batch Test", intents=[
        RestoreIntent("source_file", Capability.OPEN_FILE, resource_path="/tmp/f1.py", priority=1),
        RestoreIntent("source_file", Capability.OPEN_FILE, resource_path="/tmp/f2.py", priority=2),
        RestoreIntent("source_file", Capability.OPEN_FILE, resource_path="/tmp/f3.py", priority=3),
    ], approved=False)

    batch_res = executor.execute_plan(plan, backend, affinity)
    assert len(batch_res) == 3
    assert all(not r.success and "batch size exceeds prompt threshold" in r.detail for r in batch_res)

    # 2. Execution and Affinity positive/negative outcome scoring
    single_intent = RestoreIntent("source_file", Capability.OPEN_FILE, resource_path="/tmp/foo.py", app_id="com.microsoft.vscode")
    mock_res = LaunchResult(single_intent, True, "VS Code", "Opened", app_id="com.microsoft.vscode", focused=True)
    with patch.object(backend, "execute", return_value=mock_res):
        res = executor.execute_single(single_intent, backend, affinity)
        assert res.success is True
        assert affinity.get_preferred_app(".py") == "com.microsoft.vscode"
        assert affinity.get_affinity_distribution(".py")["com.microsoft.vscode"] == 1.0

    # 3. Dismissed outcome check
    dismissed_intent = RestoreIntent("webpage", Capability.OPEN_URL, resource_url="https://example.com", app_id="com.google.chrome", metadata={"dismissed": True})
    res_dismissed = executor.execute_single(dismissed_intent, backend, affinity)
    assert res_dismissed.dismissed is True
    assert res_dismissed.executed is False
