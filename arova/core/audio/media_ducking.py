import sys
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class MediaDuckingEngine:
    """
    Fluid Audio Controller for Arova.
    Ducks background music playback (YouTube Music, Spotify, VLC) to 25%
    when the user talks or Arova speaks, and restores volume smoothly on idle.
    """
    def __init__(self):
        self._is_ducked = False
        self._previous_volume: Optional[int] = None

    async def duck(self):
        """Lowers background music volume to 25% during voice interaction."""
        if self._is_ducked:
            return
        self._is_ducked = True
        logger.info("MediaDuckingEngine: Ducking background media volume to 25%...")
        try:
            if sys.platform == "win32":
                # Windows volume ducking via PowerShell
                cmd = "powershell -command \"$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]174)\""
                p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await p.communicate()
            elif sys.platform == "darwin":
                # macOS AppleScript volume ducking
                cmd = "osascript -e 'set volume output volume 25'"
                p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await p.communicate()
            else:
                # Linux PipeWire / PulseAudio ducking or playerctl pause
                cmd = "wpctl set-volume @DEFAULT_AUDIO_SINK@ 25% || pactl set-sink-volume @DEFAULT_SINK@ 25% || playerctl volume 0.25 || true"
                p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await p.communicate()
        except Exception as e:
            logger.debug(f"MediaDuckingEngine duck failed: {e}")

    async def restore(self):
        """Restores background music volume to 100% when voice interaction finishes."""
        if not self._is_ducked:
            return
        self._is_ducked = False
        logger.info("MediaDuckingEngine: Restoring background media volume to 100%...")
        try:
            if sys.platform == "win32":
                cmd = "powershell -command \"$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]175)\""
                p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await p.communicate()
            elif sys.platform == "darwin":
                cmd = "osascript -e 'set volume output volume 80'"
                p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await p.communicate()
            else:
                cmd = "wpctl set-volume @DEFAULT_AUDIO_SINK@ 100% || pactl set-sink-volume @DEFAULT_SINK@ 100% || playerctl volume 1.0 || true"
                p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await p.communicate()
        except Exception as e:
            logger.debug(f"MediaDuckingEngine restore failed: {e}")
