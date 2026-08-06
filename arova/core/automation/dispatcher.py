import logging
from typing import Dict, Any, Optional
from arova.core.automation.schema import CapabilityRequest, RiskLevel, NodeState

logger = logging.getLogger(__name__)

class BackendObservation:
    def __init__(self, output: str, success: bool, error: Optional[str] = None):
        self.output = output
        self.success = success
        self.error = error

class ActionBackend:
    """Base class for all capability backends."""
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        raise NotImplementedError

class CommandBackend(ActionBackend):
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        command = request.payload.get("command")
        if not command:
            return BackendObservation("", False, "No command provided in payload")
            
        if simulation_mode:
            logger.info(f"SIMULATION: Would execute terminal command: {command}")
            return BackendObservation(f"Simulated execution of: {command}", True)
            
        import asyncio
        try:
            # We use asyncio.create_subprocess_shell
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            output = ""
            if stdout:
                output += stdout.decode()
            if stderr:
                output += "\nSTDERR:\n" + stderr.decode()
                
            success = process.returncode == 0
            return BackendObservation(output.strip(), success, error=stderr.decode() if not success else None)
        except Exception as e:
            return BackendObservation("", False, str(e))

class DesktopAppBackend(ActionBackend):
    def _get_url_open_command(self, url: str) -> str:
        import sys
        if sys.platform == "win32":
            return f'start "" "{url}"'
        elif sys.platform == "darwin":
            return f"open '{url}'"
        else:
            return f"xdg-open '{url}' || brave-browser '{url}' || google-chrome '{url}' || firefox '{url}'"

    def _compute_acronym(self, text: str) -> str:
        """Extracts acronym from multi-word display name (e.g. 'Visual Studio Code' -> 'vsc')."""
        import re
        words = re.findall(r'[a-zA-Z0-9]+', text)
        if len(words) >= 2:
            return "".join(w[0].lower() for w in words)
        return ""

    def _score_match(self, query: str, app_display_name: str, exec_name: str, keywords: str = "") -> int:
        """
        Universal scoring engine for any application on earth across Linux, macOS, and Windows.
        Scores from 0 to 100 based on exact match, normalized string, acronym, word containment, and substring overlap.
        """
        import re, os
        q_lower = query.lower().strip()
        d_lower = app_display_name.lower().strip()
        e_lower = os.path.basename(exec_name).lower().strip()
        k_lower = keywords.lower().strip()

        q_clean = re.sub(r'[^a-zA-Z0-9]', '', q_lower)
        d_clean = re.sub(r'[^a-zA-Z0-9]', '', d_lower)
        e_clean = re.sub(r'[^a-zA-Z0-9]', '', e_lower)

        # 1. Exact match on executable or display name
        if q_lower == d_lower or q_lower == e_lower:
            return 100
        if q_clean == d_clean or q_clean == e_clean:
            return 95

        # 2. Acronym match (e.g. "vs code" / "vsc" matching "Visual Studio Code")
        d_acronym = self._compute_acronym(app_display_name)
        q_acronym = self._compute_acronym(query)
        if (q_clean and q_clean == d_acronym) or (q_acronym and q_acronym == d_acronym):
            return 90

        # 3. All query words contained in display name or executable
        q_words = [w for w in re.findall(r'[a-zA-Z0-9]+', q_lower) if len(w) > 1]
        if q_words and all(w in d_lower or w in e_lower or w in k_lower for w in q_words):
            return 85

        # 4. Partial substring match
        if q_clean and (q_clean in d_clean or q_clean in e_clean or d_clean in q_clean):
            return 75

        # 5. Any significant word match
        if q_words and any(w in d_lower for w in q_words if len(w) >= 3):
            return 60

        return 0

    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        app_name = request.payload.get("app_name")
        if not app_name:
            return BackendObservation("", False, "No app_name provided")
            
        import urllib.parse, sys, os, shutil, asyncio, re

        # Strip conversational prefixes
        for prefix in ["can you open ", "please open ", "open ", "launch ", "start ", "fire up ", "run ", "search for ", "search ", "look up ", "show me "]:
            if app_name.lower().startswith(prefix):
                app_name = app_name[len(prefix):].strip()
                break

        app_lower = app_name.lower().strip()

        # 1. Direct Web / Google Search Intent Detection
        if "on google" in app_lower or app_lower == "google" or app_lower.startswith("http://") or app_lower.startswith("https://"):
            clean_q = app_name.replace("on google", "").replace("google", "").strip()
            if not clean_q or app_lower == "google":
                search_url = "https://www.google.com"
            elif clean_q.startswith("http://") or clean_q.startswith("https://"):
                search_url = clean_q
            else:
                search_url = f"https://www.google.com/search?q={urllib.parse.quote(clean_q)}"
            
            if simulation_mode:
                return BackendObservation(f"Simulated web search: {search_url}", True)

            open_cmd = self._get_url_open_command(search_url)
            p = await asyncio.create_subprocess_shell(open_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await asyncio.sleep(0.5)
            return BackendObservation(f"Opened {search_url} in your browser.", True)

        # 2. Direct Domain or URL payload from LLM Action Planner (e.g. 'zomato.com', 'github.com')
        if "." in app_lower and " " not in app_lower and not app_lower.endswith("."):
            target_url = app_name if app_lower.startswith("http") else f"https://{app_name}"
            if simulation_mode:
                return BackendObservation(f"Simulated domain open: {target_url}", True)
            open_cmd = self._get_url_open_command(target_url)
            p = await asyncio.create_subprocess_shell(open_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await asyncio.sleep(0.5)
            return BackendObservation(f"Opened {target_url} in your browser for '{app_name}'.", True)

        # 3. UNIVERSAL CROSS-PLATFORM DYNAMIC APP RESOLUTION
        # Fast Alias Mapping Table for high-frequency popular apps
        APP_ALIASES = {
            "vs code": ["code", "code-oss", "codium", "visual-studio-code", "Visual Studio Code"],
            "vscode": ["code", "code-oss", "codium", "visual-studio-code", "Visual Studio Code"],
            "vsc": ["code", "code-oss", "codium", "Visual Studio Code"],
            "visual studio code": ["code", "code-oss", "codium", "visual-studio-code", "Visual Studio Code"],
            "cursor": ["cursor", "cursor-editor", "Cursor"],
            "pycharm": ["pycharm", "pycharm-community", "pycharm-professional", "PyCharm"],
            "intellij": ["idea", "intellij-idea-community", "intellij-idea-ultimate", "IntelliJ IDEA"],
            "sublime": ["subl", "sublime_text", "Sublime Text"],
            "sublime text": ["subl", "sublime_text", "Sublime Text"],
            "terminal": ["kitty", "alacritty", "gnome-terminal", "konsole", "xterm", "tilix", "foot", "wt", "cmd", "powershell", "Terminal"],
            "console": ["kitty", "alacritty", "gnome-terminal", "konsole", "wt", "cmd", "powershell"],
            "powershell": ["powershell", "pwsh"],
            "chrome": ["google-chrome-stable", "google-chrome", "chrome", "chromium", "Google Chrome"],
            "google chrome": ["google-chrome-stable", "google-chrome", "chrome", "Google Chrome"],
            "brave": ["brave-browser", "brave", "Brave Browser"],
            "brave browser": ["brave-browser", "brave", "Brave Browser"],
            "edge": ["msedge", "microsoft-edge", "Microsoft Edge"],
            "microsoft edge": ["msedge", "microsoft-edge", "Microsoft Edge"],
            "firefox": ["firefox", "firefox-esr", "Firefox"],
            "safari": ["safari", "Safari"],
            "discord": ["discord", "vesktop", "webcord", "Discord"],
            "spotify": ["spotify", "Spotify"],
            "slack": ["slack", "Slack"],
            "telegram": ["telegram-desktop", "telegram", "Telegram"],
            "vlc": ["vlc", "VLC"],
            "postman": ["postman", "Postman"],
            "obs": ["obs", "obs-studio", "OBS Studio"],
            "steam": ["steam", "Steam"],
            "calculator": ["gnome-calculator", "kcalc", "calc", "calc.exe", "Calculator"]
        }

        search_targets = [app_name]
        if app_lower in APP_ALIASES:
            search_targets.extend(APP_ALIASES[app_lower])
        search_targets = list(dict.fromkeys(search_targets))

        # --- A. CHECK SYSTEM PATH FIRST ---
        for target in search_targets:
            bin_path = shutil.which(target) or (sys.platform == "win32" and shutil.which(f"{target}.exe"))
            if bin_path:
                if simulation_mode: return BackendObservation(f"Simulated binary launch: {bin_path}", True)
                if sys.platform == "win32":
                    p = await asyncio.create_subprocess_shell(f'start "" "{bin_path}"', shell=True)
                elif sys.platform == "darwin":
                    p = await asyncio.create_subprocess_shell(f'open "{bin_path}"')
                else:
                    p = await asyncio.create_subprocess_shell(f'nohup "{bin_path}" >/dev/null 2>&1 &')
                await asyncio.sleep(0.4)
                return BackendObservation(f"Launched {app_name} ({bin_path})", True)

        # --- B. DYNAMIC OS APPLICATION CATALOG DISCOVERY ---
        best_candidate = None
        highest_score = 0

        # --- MACOS DYNAMIC CATALOG ---
        if sys.platform == "darwin":
            mac_dirs = ["/Applications", "/System/Applications", "/System/Applications/Utilities", os.path.expanduser("~/Applications")]
            for md in mac_dirs:
                if not os.path.exists(md): continue
                try:
                    for item in os.listdir(md):
                        if item.endswith(".app"):
                            app_display = item[:-4]
                            score = self._score_match(app_name, app_display, app_display)
                            if score > highest_score:
                                highest_score = score
                                best_candidate = {"type": "mac", "target": app_display, "path": os.path.join(md, item)}
                except Exception: pass

        # --- WINDOWS DYNAMIC CATALOG ---
        elif sys.platform == "win32":
            win_dirs = [
                os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
                os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps")
            ]
            for wd in win_dirs:
                if not os.path.exists(wd): continue
                try:
                    for root, _, files in os.walk(wd):
                        for f in files:
                            if f.endswith(".lnk") or f.endswith(".exe"):
                                app_display = os.path.splitext(f)[0]
                                score = self._score_match(app_name, app_display, app_display)
                                if score > highest_score:
                                    highest_score = score
                                    best_candidate = {"type": "win", "target": os.path.join(root, f)}
                except Exception: pass

        # --- LINUX DYNAMIC XDG CATALOG ---
        else:
            desktop_dirs = [
                "/usr/share/applications",
                "/usr/local/share/applications",
                os.path.expanduser("~/.local/share/applications"),
                "/var/lib/flatpak/exports/share/applications",
                os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
                "/snap/bin"
            ]
            for d in desktop_dirs:
                if not os.path.exists(d): continue
                try:
                    for fname in os.listdir(d):
                        if fname.endswith(".desktop"):
                            fpath = os.path.join(d, fname)
                            try:
                                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                                    content = f.read()
                                name_match = re.search(r'^Name\s*=\s*(.+)$', content, re.MULTILINE)
                                exec_match = re.search(r'^Exec\s*=\s*(.+)$', content, re.MULTILINE)
                                kw_match = re.search(r'^Keywords\s*=\s*(.+)$', content, re.MULTILINE)
                                if name_match and exec_match:
                                    d_name = name_match.group(1).strip()
                                    d_exec = exec_match.group(1).split()[0].replace('"', '').replace("'", "")
                                    d_kw = kw_match.group(1).strip() if kw_match else ""
                                    
                                    score = self._score_match(app_name, d_name, d_exec, d_kw)
                                    if score > highest_score:
                                        valid_bin = shutil.which(d_exec) or (os.path.exists(d_exec) and os.access(d_exec, os.X_OK))
                                        if valid_bin or d_exec:
                                            highest_score = score
                                            best_candidate = {"type": "linux", "exec": valid_bin or d_exec, "desktop_id": fname}
                            except Exception: pass
                except Exception: pass

        # --- EXECUTE BEST DYNAMIC CANDIDATE IF SCORE >= 50 ---
        if best_candidate and highest_score >= 50:
            logger.info(f"DesktopAppBackend: Universal resolver selected candidate {best_candidate} with score {highest_score} for '{app_name}'")
            if simulation_mode: return BackendObservation(f"Simulated catalog launch: {best_candidate}", True)

            # Append any trailing path/args if present in original app_name (e.g. 'code ~/PythonLearning')
            trailing_args = ""
            if " " in app_name:
                parts = app_name.split(" ", 1)
                if "/" in parts[1] or "~" in parts[1] or "." in parts[1]:
                    trailing_args = " " + os.path.expanduser(parts[1].strip())

            if best_candidate["type"] == "mac":
                p = await asyncio.create_subprocess_shell(f'open -a "{best_candidate["target"]}"{trailing_args}')
                await asyncio.sleep(0.4)
                return BackendObservation(f"Launched {app_name} on macOS", True)
            elif best_candidate["type"] == "win":
                p = await asyncio.create_subprocess_shell(f'start "" "{best_candidate["target"]}"{trailing_args}', shell=True)
                await asyncio.sleep(0.4)
                return BackendObservation(f"Launched {app_name} on Windows", True)
            else:
                exec_cmd = best_candidate["exec"]
                p = await asyncio.create_subprocess_shell(f'nohup "{exec_cmd}"{trailing_args} >/dev/null 2>&1 &')
                await asyncio.sleep(0.4)
                return BackendObservation(f"Launched {app_name} ({exec_cmd}{trailing_args})", True)

        # 4. App Not Installed on System (Clean failure — NO fake web URL opening!)
        return BackendObservation(
            f"The application '{app_name}' was not found on your system. Please verify that it is installed.",
            False,
            error=f"App '{app_name}' not installed on {sys.platform}"
        )

class OpenPathBackend(ActionBackend):
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        path = request.payload.get("path")
        if not path:
            return BackendObservation("", False, "No path provided")
            
        import sys, os, re
        
        # Clean fake hardcoded macOS/Windows user paths if present
        clean_path = path
        if "/Users/username/" in clean_path or "/home/username/" in clean_path:
            clean_path = clean_path.replace("/Users/username/", "~/").replace("/home/username/", "~/")
            
        expanded_path = os.path.expanduser(clean_path)
        
        # Ensure target directory exists before opening
        try:
            if not os.path.exists(expanded_path) and ("/" in clean_path or "\\" in clean_path or clean_path.startswith("~")):
                os.makedirs(expanded_path, exist_ok=True)
                logger.info(f"OpenPathBackend: Created directory {expanded_path}")
        except Exception as e:
            logger.debug(f"OpenPathBackend: mkdir notice: {e}")

        if sys.platform == "win32":
            command = f'explorer "{expanded_path}"'
        elif sys.platform == "darwin":
            command = f'open "{expanded_path}"'
        else:
            command = f'xdg-open "{expanded_path}"'
            
        if simulation_mode:
            logger.info(f"SIMULATION: Would open path: {expanded_path}")
            return BackendObservation(f"Simulated open path: {expanded_path}", True)
            
        import asyncio
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            return BackendObservation(f"Opened {expanded_path}", True)
        except Exception as e:
            return BackendObservation("", False, str(e))

class MediaBackend(ActionBackend):
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        cmd_type = request.payload.get("command")
        if not cmd_type:
            return BackendObservation("", False, "No command provided")
            
        import sys
        if sys.platform == "win32":
            command = "echo 'Media control requires additional libraries on Windows'"
        elif sys.platform == "darwin":
            mac_cmd = {
                "play_pause": "playpause",
                "next_track": "next track",
                "previous_track": "previous track",
                "stop": "stop"
            }.get(cmd_type, "playpause")
            command = f"osascript -e 'tell application \"Music\" to {mac_cmd}' || osascript -e 'tell application \"Spotify\" to {mac_cmd}'"
        else:
            playerctl_map = {
                "play_pause": "play-pause",
                "next_track": "next",
                "previous_track": "previous",
                "stop": "stop"
            }
            player_cmd = playerctl_map.get(cmd_type, cmd_type)
            command = f"playerctl {player_cmd}"
        
        if simulation_mode:
            logger.info(f"SIMULATION: Would execute media command: {command}")
            return BackendObservation(f"Simulated media command: {command}", True)
            
        import asyncio
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            success = process.returncode == 0
            return BackendObservation("Media command executed", success, error=stderr.decode() if stderr and not success else None)
        except Exception as e:
            return BackendObservation("", False, str(e))

class WebSearchBackend(ActionBackend):
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        query = request.payload.get("query")
        if not query:
            return BackendObservation("", False, "No query provided")
            
        import urllib.parse
        import webbrowser
        
        encoded_query = urllib.parse.quote(query)
        url = f"https://google.com/search?q={encoded_query}"
        
        if simulation_mode:
            logger.info(f"SIMULATION: Would search web: {query}")
            return BackendObservation(f"Simulated search: {query}", True)
            
        try:
            webbrowser.open(url)
            return BackendObservation("Web search launched", True)
        except Exception as e:
            return BackendObservation("", False, str(e))

class VolumeBackend(ActionBackend):
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        level = request.payload.get("level")
        if level is None:
            return BackendObservation("", False, "No volume level provided")
            
        import sys
        if sys.platform == "win32":
            command = "echo 'Volume control requires nircmd or PowerShell script on Windows'"
        elif sys.platform == "darwin":
            # macOS uses a 0-100 scale for output volume
            command = f"osascript -e 'set volume output volume {level}'"
        else:
            # Standard pipewire wpctl command, fallback to pactl
            command = f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {level}% || pactl set-sink-volume @DEFAULT_SINK@ {level}%"
        
        if simulation_mode:
            logger.info(f"SIMULATION: Would execute volume command: {command}")
            return BackendObservation(f"Simulated volume set to: {level}%", True)
            
        import asyncio
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            success = process.returncode == 0
            return BackendObservation(f"Volume set to {level}%", success, error=stderr.decode() if stderr and not success else None)
        except Exception as e:
            return BackendObservation("", False, str(e))

class ScreenshotBackend(ActionBackend):
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        import time, os
        filename = f"screenshot_{int(time.time())}.png"
        filepath = os.path.expanduser(f"~/Pictures/{filename}")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        import sys
        if sys.platform == "win32":
            command = "echo 'Screenshot requires powershell or Snipping Tool'"
        elif sys.platform == "darwin":
            command = f"screencapture -x '{filepath}'"
        else:
            from arova.core.context import detect_screenshot_tool
            tool = detect_screenshot_tool()
            if not tool:
                return BackendObservation("", False, "No screenshot tool detected (grim, scrot, gnome-screenshot, spectacle, etc.)")
            
            if tool == "grim":
                command = f"grim '{filepath}'"
            elif tool == "grimblast":
                command = f"grimblast save screen '{filepath}'"
            elif tool == "scrot":
                command = f"scrot '{filepath}'"
            elif tool == "gnome-screenshot":
                command = f"gnome-screenshot -f '{filepath}'"
            elif tool == "spectacle":
                command = f"spectacle -f -b -n -o '{filepath}'"
            elif tool == "flameshot":
                command = f"flameshot full -p '{filepath}'"
            elif tool == "import":
                command = f"import -window root '{filepath}'"
            else:
                command = f"{tool} '{filepath}'"
        
        if simulation_mode:
            logger.info(f"SIMULATION: Would take screenshot: {command}")
            return BackendObservation(f"Simulated screenshot saved to {filepath}", True)
            
        import asyncio
        try:
            # Step 1: Take screenshot
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
                success = process.returncode == 0
            except asyncio.TimeoutError:
                process.terminate()
                return BackendObservation("", False, "Screenshot tool timed out after 5 seconds. It may be waiting for interactive input.")
            
            # Step 2: Copy to clipboard if successful
            if success:
                clip_cmd = ""
                if sys.platform == "win32":
                    clip_cmd = f"powershell -command \"Set-Clipboard -Path '{filepath}'\""
                elif sys.platform == "darwin":
                    clip_cmd = f"osascript -e 'set the clipboard to (read (POSIX file \"{filepath}\") as JPEG picture)'"
                else:
                    from arova.core.context import detect_display_server, _command_exists
                    if detect_display_server() == "wayland" and _command_exists("wl-copy"):
                        clip_cmd = f"wl-copy < '{filepath}'"
                    elif _command_exists("xclip"):
                        clip_cmd = f"xclip -selection clipboard -target image/png -i '{filepath}'"
                
                if clip_cmd:
                    clip_proc = await asyncio.create_subprocess_shell(
                        clip_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await clip_proc.communicate()
            
            return BackendObservation(f"Screenshot taken and saved to {filepath} (and copied to clipboard)", success, error=stderr.decode() if stderr and not success else None)
        except Exception as e:
            return BackendObservation("", False, str(e))

class PlayMusicBackend(ActionBackend):
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        query = request.payload.get("song_query")
        if not query:
            return BackendObservation("", False, "No song query provided")
            
        if simulation_mode:
            logger.info(f"SIMULATION: Would search and play music: {query}")
            return BackendObservation(f"Simulated playing music: {query}", True)
            
        import asyncio
        import webbrowser
        try:
            # Use yt-dlp to get the video ID for the first search result
            command = f"yt-dlp \"ytsearch1:{query}\" --get-id"
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            success = process.returncode == 0
            
            if success and stdout:
                video_id = stdout.decode().strip()
                if video_id:
                    url = f"https://music.youtube.com/watch?v={video_id}"
                    webbrowser.open(url)
                    return BackendObservation(f"Playing music: {url}", True)
            
            return BackendObservation("", False, f"Failed to find music: {stderr.decode() if stderr else 'No results'}")
        except Exception as e:
            return BackendObservation("", False, str(e))

class FocusWindowBackend(ActionBackend):
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        window_name = request.payload.get("window_name")
        if not window_name:
            return BackendObservation("", False, "No window_name provided")
        
        import sys, asyncio, shlex
        safe_name = shlex.quote(window_name)
        if sys.platform == "darwin":
            command = f"osascript -e 'tell application \"{window_name}\" to activate'"
        elif sys.platform == "win32":
            command = f"powershell -command \"(New-Object -ComObject WScript.Shell).AppActivate('{window_name}')\""
        else:
            command = f"wmctrl -a {safe_name}"
            
        if simulation_mode:
            return BackendObservation(f"Simulated focusing window: {window_name}", True)
            
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            success = process.returncode == 0
            
            # For Linux, try hyprctl if wmctrl fails
            if not success and sys.platform.startswith("linux"):
                hypr_cmd = f"hyprctl dispatch focuswindow {safe_name}"
                process = await asyncio.create_subprocess_shell(hypr_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await process.communicate()
                success = process.returncode == 0
                
            return BackendObservation(f"Focused window {window_name}", success, error=stderr.decode() if stderr and not success else None)
        except Exception as e:
            return BackendObservation("", False, str(e))

class CloseWindowBackend(ActionBackend):
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        window_name = request.payload.get("window_name")
        if not window_name:
            return BackendObservation("", False, "No window_name provided")
        
        import sys, asyncio, shlex
        safe_name = shlex.quote(window_name)
        if sys.platform == "darwin":
            command = f"osascript -e 'tell application \"{window_name}\" to quit'"
        elif sys.platform == "win32":
            command = f"taskkill /IM {safe_name}.exe /F"
        else:
            command = f"wmctrl -c {safe_name}"
            
        if simulation_mode:
            return BackendObservation(f"Simulated closing window: {window_name}", True)
            
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            success = process.returncode == 0
            
            # For Linux, try hyprctl if wmctrl fails
            if not success and sys.platform.startswith("linux"):
                hypr_cmd = f"hyprctl dispatch closewindow {safe_name}"
                process = await asyncio.create_subprocess_shell(hypr_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await process.communicate()
                success = process.returncode == 0
                
            return BackendObservation(f"Closed window {window_name}", success, error=stderr.decode() if stderr and not success else None)
        except Exception as e:
            return BackendObservation("", False, str(e))

class AnalyzeScreenBackend(ActionBackend):
    def __init__(self, orchestrator: Optional[Any] = None):
        self.orchestrator = orchestrator

    async def _capture_target_windows(self, query: str, base_dir: str) -> List[str]:
        import sys, os, time, json, shutil, asyncio
        captured_paths = []
        q_lower = query.lower()
        q_words = [w for w in q_lower.replace('?', '').replace(',', '').split() if len(w) > 3 and w not in ('that', 'this', 'have', 'been', 'good', 'about', 'with', 'from')]

        timestamp = int(time.time() * 1000)

        if sys.platform.startswith("linux"):
            his = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
            xdg_runtime = os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
            if not his and os.path.exists(f"{xdg_runtime}/hypr"):
                try:
                    dirs = [d for d in os.listdir(f"{xdg_runtime}/hypr") if not d.startswith(".")]
                    if dirs:
                        his = dirs[0]
                except Exception:
                    pass
            sock_path = f'{xdg_runtime}/hypr/{his}/.socket.sock' if his else None

            def _send_hypr_cmd(cmd_str: str):
                import subprocess
                hyprctl_bin = "/usr/bin/hyprctl" if os.path.exists("/usr/bin/hyprctl") else "hyprctl"
                if "workspace " in cmd_str:
                    ws_id = cmd_str.split("workspace ")[1].strip()
                    lua_cmd = f"hl.dsp.focus{{ workspace = {ws_id} }}"
                elif "focuswindow " in cmd_str:
                    win_target = cmd_str.split("focuswindow ")[1].strip()
                    if not win_target.startswith("address:") and not win_target.startswith("class:"):
                        win_target = f"class:{win_target}"
                    lua_cmd = f"hl.dsp.focus{{ window = \"{win_target}\" }}"
                else:
                    lua_cmd = f"hl.dsp.exec_cmd('hyprctl dispatch {cmd_str}')"

                try:
                    subprocess.run([hyprctl_bin, "dispatch", lua_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                except Exception as e:
                    logger.warning(f"AnalyzeScreenBackend: _send_hypr_cmd failed: {e}")

            if shutil.which("hyprctl") or os.path.exists("/usr/bin/hyprctl"):
                try:
                    hyprctl_bin = "/usr/bin/hyprctl" if os.path.exists("/usr/bin/hyprctl") else "hyprctl"
                    # 1. Get current active window & workspace
                    act_proc = await asyncio.create_subprocess_exec(hyprctl_bin, "activewindow", "-j", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    act_out, _ = await act_proc.communicate()
                    active_ws = 1
                    active_class = "frontend"
                    if act_proc.returncode == 0 and act_out:
                        act_data = json.loads(act_out.decode('utf-8', errors='ignore'))
                        active_ws = act_data.get("workspace", {}).get("id", 1)
                        active_class = act_data.get("class", "frontend")

                    # 2. Score and select target client across all workspaces
                    proc = await asyncio.create_subprocess_exec(hyprctl_bin, "clients", "-j", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                    stdout, _ = await proc.communicate()
                    if proc.returncode == 0 and stdout:
                        clients = json.loads(stdout.decode('utf-8', errors='ignore'))
                        scored_clients = []
                        
                        for client in clients:
                            cls = client.get("class", "").lower()
                            title = client.get("title", "").lower()
                            # Never target Arova UI itself or terminal dev log windows unless explicitly named
                            if cls in ("frontend", "arova") or "arova" in title and cls == "frontend":
                                continue
                                
                            score = 0
                            # Media type affinity
                            if any(k in q_lower for k in ["youtube", "yt", "video", "watch", "stream", "channel", "play", "browser", "tab"]):
                                if any(app in cls or app in title for app in ["brave", "chrome", "firefox", "edge", "safari", "opera", "vlc", "mpv", "youtube"]):
                                    score += 150
                            elif any(k in q_lower for k in ["code", "vscode", "antigravity", "editor", "script", "terminal", "ide", "bug", "error", "programming", "line"]):
                                if any(app in cls or app in title for app in ["antigravity", "code", "cursor", "nvim", "vim", "sublime", "jetbrains", "kitty", "alacritty"]):
                                    score += 150
                            else:
                                # General content app fallback boost for non-specific queries
                                if any(app in cls or app in title for app in ["brave", "chrome", "firefox", "edge", "code", "antigravity", "vlc", "mpv", "libreoffice"]):
                                    score += 50
                                    
                            # Keyword matching in title and class
                            for w in q_words:
                                if w in title:
                                    score += 60
                                if w in cls:
                                    score += 40
                                    
                            if score > 0:
                                scored_clients.append((score, client))

                        target_client = None
                        if scored_clients:
                            scored_clients.sort(key=lambda x: x[0], reverse=True)
                            target_client = scored_clients[0][1]
                            logger.info(f"AnalyzeScreenBackend: Selected window '{target_client.get('class')}' (Title: '{target_client.get('title')}') with score {scored_clients[0][0]} for query: '{query}'")

                        if target_client:
                            t_ws = target_client.get("workspace", {}).get("id", active_ws)
                            t_cls = target_client.get("class", "")
                            t_addr = target_client.get("address", "")

                            # Focus-Capture-Restore!
                            logger.info(f"AnalyzeScreenBackend: Switching to workspace {t_ws} and focusing '{t_cls}'...")
                            _send_hypr_cmd(f"workspace {t_ws}")
                            if t_addr:
                                _send_hypr_cmd(f"focuswindow address:{t_addr}")
                            else:
                                _send_hypr_cmd(f"focuswindow class:{t_cls}")
                            await asyncio.sleep(0.35)

                            target_path = os.path.join(base_dir, f"target_focus_{timestamp}.png")
                            geom_cmd = f"grim '{target_path}'"

                            p = await asyncio.create_subprocess_shell(geom_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                            await p.communicate()

                            # Instantly restore active workspace & focus back to Arova!
                            logger.info(f"AnalyzeScreenBackend: Restoring workspace {active_ws} and focusing '{active_class}'...")
                            _send_hypr_cmd(f"workspace {active_ws}")
                            _send_hypr_cmd(f"focuswindow class:{active_class}")

                            if p.returncode == 0 and os.path.exists(target_path) and os.path.getsize(target_path) > 1000:
                                captured_paths.append(target_path)
                except Exception as e:
                    logger.debug(f"Focus-Capture-Restore Hyprland failed: {e}")

        # Fallback to standard full screenshot if focus-capture didn't produce an image
        if not captured_paths:
            full_path = os.path.join(base_dir, f"full_screen_{timestamp}.png")
            if sys.platform == "darwin":
                cmd = f"screencapture -x '{full_path}'"
            elif sys.platform == "win32":
                cmd = f"powershell -command \"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait('{{PRTSC}}')\""
            else:
                cmd = f"grim '{full_path}' || scrot '{full_path}' || import -window root '{full_path}'"

            p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await asyncio.wait_for(p.communicate(), timeout=5.0)
            if os.path.exists(full_path):
                captured_paths.append(full_path)

        return captured_paths

    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        query = request.payload.get("query", "Describe the screen")
        if simulation_mode:
            return BackendObservation(f"Simulated screen analysis for query: {query}", True)
            
        import sys, asyncio, time, os, base64
        base_dir = os.path.expanduser("~/Pictures")
        os.makedirs(base_dir, exist_ok=True)
        
        captured_paths = []
        try:
            captured_paths = await self._capture_target_windows(query, base_dir)
            if not captured_paths:
                return BackendObservation("", False, "Failed to capture any window or screen screenshot.")
                
            image_content_parts = [{
                "type": "text", 
                "text": f"User Query: {query}\n"
                        "Analyze the attached window/screen screenshot(s) and answer the user's question directly with clean, calm, serene, and minimal markdown.\n"
                        "CALM & MINIMAL TYPOGRAPHY DIRECTIVES:\n"
                        "- Present information in a clean, elegant, minimal, and serene tone so the user can read calmly.\n"
                        "- Use short, clear paragraphs and concise bullet points.\n"
                        "- AVOID VISUAL CLUTTER: Do NOT use horizontal divider lines (`---`), do NOT use nested numbered sub-lists, and do NOT over-bold every word or sentence.\n"
                        "- Use clean section headers (e.g. `### Direct Answer`, `### Breakdown`).\n"
                        "- Write brand names correctly without period splits (e.g. 'YouTube', 'PyCharm', 'VS Code')."
            }]
            for path in captured_paths:
                with open(path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode('utf-8')
                    image_content_parts.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_data}"}})
                    
            for path in captured_paths:
                try:
                    os.remove(path)
                except OSError:
                    pass
                    
            messages = [{"role": "user", "content": image_content_parts}]
            
            from arova.core.providers.capabilities import Capability
            from arova.core.models.orchestrator import ModelOrchestrator, ReasoningDepth
            
            sys_prompt = "You are Arova Vision. Provide detailed, well-formatted markdown analysis. Ensure all bold syntax and markdown tags are properly paired and closed."
            orchestrator = self.orchestrator or ModelOrchestrator({})
            if hasattr(orchestrator, 'router'):
                result_text = await orchestrator.router.generate(messages, sys_prompt, capability=Capability.VISION, max_tokens=3000)
            elif hasattr(orchestrator, 'generate'):
                result_text = await orchestrator.generate(messages, sys_prompt, depth=ReasoningDepth.STANDARD)
            else:
                result_text = "Vision provider unavailable."
            
            if result_text and result_text.startswith("⚠"):
                return BackendObservation("I captured your target window, but vision analysis requires a valid Google Gemini API key. Please add a valid Gemini API key in Settings.", True)
            
            # Post-process markdown formatting to prevent broken bold tags or split proper nouns
            def _clean_markdown(txt: str) -> str:
                if not txt:
                    return txt
                txt = txt.replace("You. Tube", "YouTube").replace("You.Tube", "YouTube")
                txt = txt.replace("Py. Charm", "PyCharm").replace("Py.Charm", "PyCharm")
                txt = txt.replace("Visual Studio. Code", "VS Code")
                lines = txt.split("\n")
                cleaned = []
                for line in lines:
                    if line.count("**") % 2 != 0:
                        if line.startswith("**"):
                            line = line + "**"
                        else:
                            line = line.replace("**", "")
                    cleaned.append(line)
                return "\n".join(cleaned)

            return BackendObservation(_clean_markdown(result_text), True)
        except Exception as e:
            for path in captured_paths:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            return BackendObservation("", False, f"Failed to capture or analyze screen: {e}")

class ListOpenAppsBackend(ActionBackend):
    async def execute(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        from arova.core.platform.services.backend import PlatformBackend
        if simulation_mode:
            logger.info("SIMULATION: Would list open apps")
            return BackendObservation("Simulated open apps: Terminal, Chrome", True)
        try:
            backend = PlatformBackend.create()
            windows = backend.get_open_windows()
            if not windows:
                return BackendObservation("No open applications found.", True)
            msg = "Currently open applications:\n" + "\n".join([f"- {w}" for w in windows])
            return BackendObservation(msg, True)
        except Exception as e:
            return BackendObservation("", False, f"Failed to list open apps: {e}")

class ActionDispatcher:
    """
    Routes abstract CapabilityRequests to their concrete backend implementations.
    """
    def __init__(self, orchestrator: Optional[Any] = None, workspace_manager: Optional[Any] = None):
        self.orchestrator = orchestrator
        self.workspace_manager = workspace_manager
        self._backends: Dict[str, ActionBackend] = {
            "CommandBackend": CommandBackend(),
            "run_command": CommandBackend(),
            "open_app": DesktopAppBackend(),
            "list_open_apps": ListOpenAppsBackend(),
            "focus_window": FocusWindowBackend(),
            "close_window": CloseWindowBackend(),
            "analyze_screen": AnalyzeScreenBackend(orchestrator=orchestrator),
            "open_path": OpenPathBackend(),
            "media_control": MediaBackend(),
            "search_web": WebSearchBackend(),
            "set_volume": VolumeBackend(),
            "play_music": PlayMusicBackend(),
            "screenshot": ScreenshotBackend()
        }

    async def dispatch(self, request: CapabilityRequest, simulation_mode: bool = False) -> BackendObservation:
        backend = self._backends.get(request.capability)
        if not backend:
            error_msg = f"No backend registered for capability: {request.capability}"
            logger.error(error_msg)
            return BackendObservation("", False, error_msg)
            
        logger.info(f"ActionDispatcher: Routing {request.action} -> {request.capability}")
        res = await backend.execute(request, simulation_mode=simulation_mode)
        if res and res.success and self.workspace_manager:
            try:
                payload = request.payload if hasattr(request, 'payload') and isinstance(request.payload, dict) else {}
                target_id = payload.get("path") or payload.get("url") or payload.get("app") or payload.get("query") or payload.get("command") or request.action
                if target_id:
                    self.workspace_manager.ingest_fragment({
                        "source_identity": str(target_id),
                        "provider_id": request.capability,
                        "activity_summary": f"Executed action {request.action}: {target_id}"
                    })
            except Exception as e:
                logger.debug(f"ActionDispatcher fragment ingest warning: {e}")
        return res
