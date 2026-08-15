import logging
import subprocess
import threading
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass
from arova.core.events import RuntimeEventBus
from arova.core.time import RuntimeClock

@dataclass
class AudioCapabilities:
    duplex: bool = True
    echo_cancel: bool = False
    low_latency: bool = True

class PlaybackPriority:
    BACKGROUND = 10
    NOTIFICATION = 20
    TTS_RESPONSE = 30
    ALARM = 40

class DuckPolicy:
    NONE = "none"
    DUCK = "duck"
    PAUSE = "pause"
    STOP = "stop"

class MicrophoneSession:
    """
    Arbitrates single-capture device access and multiplexes chunks to subscribers.
    Prevents ALSA/Pipewire double-open crashes.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers: Dict[str, dict] = {}
        self._is_capturing = False
        self._capture_generation_id = 0
        
    def subscribe(self, name: str, priority: int, callback: Callable[[bytes, int], None]) -> bool:
        with self._lock:
            self._subscribers[name] = {"priority": priority, "callback": callback}
            if not self._is_capturing:
                self._start_capture()
            return True
            
    def unsubscribe(self, name: str):
        should_stop = False
        with self._lock:
            if name in self._subscribers:
                del self._subscribers[name]
            if not self._subscribers and self._is_capturing:
                should_stop = True
        if should_stop:
            self._stop_capture()
                
    def _start_capture(self):
        self._is_capturing = True
        self._capture_generation_id += 1
        
        def audio_callback(indata, frames, time, status):
            if not self._is_capturing:
                return
            if status:
                logging.warning(f"Microphone status: {status}")
            # indata is numpy array, we want raw bytes for webrtcvad/stt
            # shape is (frames, channels), dtype=int16
            chunk = indata.tobytes()
            self.push_chunk(chunk, 16000)

        try:
            import sounddevice as sd
            self._stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype='int16',
                blocksize=480, # 30ms at 16kHz for WebRTC VAD (and >400 for openwakeword)
                callback=audio_callback
            )
            self._stream.start()
            logging.info(f"MicrophoneSession: hardware capture started (gen {self._capture_generation_id}).")
        except Exception as e:
            logging.warning(f"MicrophoneSession: sounddevice unavailable ({e}); running in audio-disabled mode.")
            logging.error(f"Failed to start hardware capture: {e}")
            self._is_capturing = False
        
    def _stop_capture(self):
        stream_to_close = None
        with self._lock:
            if not self._is_capturing and not getattr(self, '_stream', None):
                return
            self._is_capturing = False
            stream_to_close = getattr(self, '_stream', None)
            self._stream = None
            
        if stream_to_close:
            try:
                try:
                    stream_to_close.abort()
                except Exception:
                    stream_to_close.stop()
                stream_to_close.close()
            except Exception as e:
                logging.error(f"Error stopping audio capture stream: {e}")
        logging.info("MicrophoneSession: hardware capture stopped.")
        
    def push_chunk(self, chunk: bytes, sample_rate: int):
        """Called by the physical capture thread to fan-out to subscribers."""
        if not self._is_capturing:
            return
        with self._lock:
            if not self._is_capturing or not self._subscribers:
                return
            # Sort by priority descending
            subs = sorted(self._subscribers.values(), key=lambda x: x["priority"], reverse=True)
            for sub in subs:
                try:
                    sub["callback"](chunk, sample_rate)
                except Exception as e:
                    logging.error(f"Error in MicrophoneSession subscriber: {e}")

class AudioSessionManager:
    """
    Manages audio routing, playback ownership, and focus negotiation.
    Abstracts Linux backends (Pipewire first).
    """
    def __init__(self, event_bus: RuntimeEventBus):
        self._event_bus = event_bus
        self._capabilities = AudioCapabilities()
        self._active_playback_pid: Optional[int] = None
        self._playback_priority: int = 0
        self._playback_generation_id: int = 0
        self._playback_lock = threading.Lock()
        
        self.microphone = MicrophoneSession()
        
    def request_playback(self, filepath: str, priority: int, duck_policy: str = DuckPolicy.DUCK, turn_id: Optional[str] = None) -> bool:
        with self._playback_lock:
            if self._active_playback_pid is not None:
                if priority > self._playback_priority:
                    self._stop_current_playback_locked()
                else:
                    logging.warning("Playback rejected (lower priority active).")
                    return False
            
            self._playback_generation_id += 1
            current_gen = self._playback_generation_id
            
            try:
                # ffplay is the most robust player for mp3 generated by edge-tts
                proc = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._active_playback_pid = proc.pid
                self._playback_priority = priority
                
                threading.Thread(target=self._wait_playback, args=(proc, current_gen), daemon=True).start()
                return True
            except FileNotFoundError:
                try:
                    proc = subprocess.Popen(["pw-play", filepath], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self._active_playback_pid = proc.pid
                    self._playback_priority = priority
                    threading.Thread(target=self._wait_playback, args=(proc, current_gen), daemon=True).start()
                    return True
                except FileNotFoundError:
                    logging.error("No audio backend found (ffplay/pw-play missing).")
                    self._event_bus.emit("voice", "AUDIO_BACKEND_LOST")
                    return False

    def preemptive_stop(self):
        with self._playback_lock:
            self._stop_current_playback_locked()

    def _stop_current_playback_locked(self):
        if self._active_playback_pid is not None:
            try:
                import os, signal
                os.kill(self._active_playback_pid, signal.SIGTERM)
            except OSError:
                pass
            self._active_playback_pid = None
            self._playback_priority = 0
            self._playback_generation_id += 1 # Invalidate any waiting waiters

    def _wait_playback(self, proc, generation_id: int):
        proc.wait()
        with self._playback_lock:
            if self._active_playback_pid == proc.pid and self._playback_generation_id == generation_id:
                self._active_playback_pid = None
                self._playback_priority = 0
