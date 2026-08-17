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
                # Native Win32 volume ducking
                try:
                    import ctypes
                    # VK_VOLUME_DOWN = 0xAE (174)
                    for _ in range(12):
                        ctypes.windll.user32.keybd_event(0xAE, 0, 0, 0)
                        ctypes.windll.user32.keybd_event(0xAE, 0, 2, 0)
                except Exception:
                    pass
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
        """Restores background music volume to normal when voice interaction finishes."""
        if not self._is_ducked:
            return
        self._is_ducked = False
        logger.info("MediaDuckingEngine: Restoring background media volume...")
        try:
            if sys.platform == "win32":
                try:
                    import ctypes
                    # VK_VOLUME_UP = 0xAF (175)
                    for _ in range(12):
                        ctypes.windll.user32.keybd_event(0xAF, 0, 0, 0)
                        ctypes.windll.user32.keybd_event(0xAF, 0, 2, 0)
                except Exception:
                    pass
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
