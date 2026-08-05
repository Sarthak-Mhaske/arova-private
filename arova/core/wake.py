from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

class WakeWordSetupError(Exception):
    """Exception raised for dependency or setup errors in the wake word module."""
    pass

def _import_openwakeword() -> Any:
    try:
        import openwakeword
        from openwakeword.model import Model
        return Model
    except ImportError:
        return None

def _import_pyaudio() -> Any:
    try:
        import pyaudio
        return pyaudio
    except ImportError:
        return None

def _import_numpy() -> Any:
    try:
        import numpy as np
        return np
    except ImportError:
        return None

def check_wake_dependencies() -> dict[str, bool]:
    """Check if all required dependencies for wake word detection are installed."""
    return {
        "openwakeword": _import_openwakeword() is not None,
        "pyaudio": _import_pyaudio() is not None,
        "numpy": _import_numpy() is not None,
    }

def wake_listener_available() -> bool:
    """Return True if all wake dependencies are successfully loaded."""
    return all(check_wake_dependencies().values())

def get_wake_config(config: dict[str, Any]) -> dict[str, Any]:
    """Extract and normalize wake configuration, ensuring sane defaults."""
    wake_cfg = config.get("wake", {})
    
    # Defaults
    enabled = bool(wake_cfg.get("enabled", True))
    wake_word = str(wake_cfg.get("wake_word", "alexa"))
    model_path = str(wake_cfg.get("model_path", "~/.config/hyprvoice/models/alexa.onnx"))
    
    try:
        threshold = float(wake_cfg.get("threshold", 0.5))
    except (ValueError, TypeError):
        threshold = 0.5
        
    try:
        sample_rate = int(wake_cfg.get("sample_rate", 16000))
    except (ValueError, TypeError):
        sample_rate = 16000
        
    try:
        frame_length = int(wake_cfg.get("frame_length", 1280))
    except (ValueError, TypeError):
        frame_length = 1280
        
    try:
        cooldown_seconds = float(wake_cfg.get("cooldown_seconds", 2.0))
    except (ValueError, TypeError):
        cooldown_seconds = 2.0
        
    # Expand path
    if model_path:
        model_path = os.path.expanduser(model_path)
        
    return {
        "enabled": enabled,
        "wake_word": wake_word,
        "model_path": model_path,
        "threshold": threshold,
        "sample_rate": sample_rate,
        "frame_length": frame_length,
        "cooldown_seconds": cooldown_seconds,
    }

def build_openwakeword_model(ModelClass: Any, model_path: str, wake_word: str) -> Any:
    target = model_path if (model_path and os.path.exists(model_path)) else wake_word
    if not target:
        raise WakeWordSetupError("No configured model_path found and no default wake_word specified.")
    
    try:
        return ModelClass(wakeword_models=[target])
    except TypeError:
        try:
            return ModelClass()
        except Exception as e:
            raise WakeWordSetupError(f"Failed to instantiate OpenWakeWord fallback: {e}")
    except Exception as e:
        raise WakeWordSetupError(f"Failed to instantiate OpenWakeWord: {e}")

class WakeWordListener:
    """A blocking listener that manages PyAudio and OpenWakeWord detection loops."""
    
    def __init__(self, config: dict[str, Any]):
        self.config = get_wake_config(config)
        self.is_running = False
        self._muted = False
        self._pa = None
        self._stream = None
        self._model = None
        self._last_detect_time = 0.0

    def set_muted(self, muted: bool):
        self._muted = muted
        if muted and self._stream:
            try:
                self._stream.stop_stream()
            except Exception:
                pass
        elif not muted and self._stream and hasattr(self._stream, "is_stopped") and self._stream.is_stopped():
            try:
                self._stream.start_stream()
            except Exception:
                pass

    def _setup(self) -> None:
        """Initialize dependencies and models lazily."""
        if not wake_listener_available():
            raise WakeWordSetupError("Missing required dependencies: openwakeword, pyaudio, and numpy must be installed.")
            
        pyaudio = _import_pyaudio()
        Model = _import_openwakeword()
        
        self._model = build_openwakeword_model(Model, self.config["model_path"], self.config["wake_word"])
            
        try:
            self._pa = pyaudio.PyAudio()
            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.config["sample_rate"],
                input=True,
                frames_per_buffer=self.config["frame_length"]
            )
        except Exception as e:
            self.stop()
            raise WakeWordSetupError(f"Failed to open audio stream: {e}")

    def start(self, on_detect: Callable[[], None] | None = None) -> None:
        """Alias for listen_forever in a blocking context, or intended for future thread wrap."""
        self.listen_forever(on_detect)

    def listen_forever(self, on_detect: Callable[[], None] | None = None) -> None:
        """Start the blocking audio capture and prediction loop."""
        self._setup()
        self.is_running = True
        
        import numpy as np
        
        try:
            while self.is_running:
                if self._muted:
                    time.sleep(0.2)
                    continue

                if self._stream is None:
                    time.sleep(0.2)
                    continue

                data = self._stream.read(self.config["frame_length"], exception_on_overflow=False)
                # Convert bytes to numpy array
                audio_data = np.frombuffer(data, dtype=np.int16)
                
                # Predict
                prediction = self._model.predict(audio_data)
                
                # We assume the prediction is a dict mapping model names to scores
                threshold = self.config["threshold"]
                detected = False
                
                if isinstance(prediction, dict):
                    for mdl_name, score in prediction.items():
                        if score >= threshold:
                            detected = True
                            break
                        
                if detected:
                    now = time.time()
                    if now - self._last_detect_time > self.config["cooldown_seconds"]:
                        self._last_detect_time = now
                        
                        # Stop stream to free ALSA/audio device for recording
                        if self._stream is not None:
                            try:
                                self._stream.stop_stream()
                                self._stream.close()
                            except Exception:
                                pass
                            self._stream = None
                            
                        if on_detect:
                            on_detect()
                        else:
                            print(f"Wake word detected: {self.config['wake_word']}")
                            
                        # Reopen stream if still running
                        if self.is_running and self._pa is not None:
                            import pyaudio
                            try:
                                self._stream = self._pa.open(
                                    format=pyaudio.paInt16,
                                    channels=1,
                                    rate=self.config["sample_rate"],
                                    input=True,
                                    frames_per_buffer=self.config["frame_length"]
                                )
                            except Exception:
                                self._stream = None
        finally:
            self.stop()

    def stop(self) -> None:
        """Cleanly stop the stream and terminate PyAudio."""
        self.is_running = False
        
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
            
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None
