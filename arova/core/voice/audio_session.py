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
        
        try:
            import sounddevice as sd
            import numpy as np

            # Query default input device to see supported channels & samplerate
            device_info = sd.query_devices(kind='input')
            native_rate = int(device_info.get('default_samplerate', 16000))
            max_input_channels = int(device_info.get('max_input_channels', 1))
            target_rate = 16000

            def audio_callback(indata, frames, time_info, status):
                if not self._is_capturing:
                    return
                if status:
                    logging.debug(f"Microphone status: {status}")
                
                try:
                    # Convert to mono if multi-channel
                    if indata.ndim > 1 and indata.shape[1] > 1:
                        mono_data = indata.mean(axis=1).astype(np.int16)
                    else:
                        mono_data = indata.flatten().astype(np.int16)

                    # Resample to 16000Hz if device rate differs
                    if native_rate != target_rate and len(mono_data) > 0:
                        num_target_samples = int(len(mono_data) * target_rate / native_rate)
                        if num_target_samples > 0:
                            indices = np.linspace(0, len(mono_data) - 1, num_target_samples)
                            resampled = np.interp(indices, np.arange(len(mono_data)), mono_data).astype(np.int16)
                            chunk = resampled.tobytes()
                        else:
                            chunk = mono_data.tobytes()
                    else:
                        chunk = mono_data.tobytes()

                    self.push_chunk(chunk, target_rate)
                except Exception as cb_err:
                    logging.debug(f"audio_callback processing error: {cb_err}")

            # Try opening at 16000Hz first; if driver errors, fall back to native_rate
            stream = None
            try:
                stream = sd.InputStream(
                    samplerate=16000,
                    channels=1,
                    dtype='int16',
                    blocksize=480,
                    callback=audio_callback
                )
                native_rate = 16000
            except Exception as e_16k:
                logging.info(f"MicrophoneSession: 16kHz direct open fallback ({e_16k}). Opening with hardware native rate ({native_rate}Hz, {max_input_channels}ch)...")
                channels = max(1, min(max_input_channels, 2))
                block_size = max(480, int(native_rate * 0.03))
                stream = sd.InputStream(
                    samplerate=native_rate,
                    channels=channels,
                    dtype='int16',
                    blocksize=block_size,
                    callback=audio_callback
                )

            self._stream = stream
            self._stream.start()
            logging.info(f"MicrophoneSession: hardware capture active (rate={native_rate}Hz, target={target_rate}Hz, gen={self._capture_generation_id}).")
        except Exception as e:
            logging.warning(f"MicrophoneSession: sounddevice unavailable ({e}); running in audio-disabled mode.")
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
