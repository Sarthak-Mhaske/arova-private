from __future__ import annotations

import os
import shutil
import subprocess
import time
import math
import struct
import wave
from datetime import datetime
from pathlib import Path
from typing import Any

def _command_exists(name: str) -> bool:
    return shutil.which(name) is not None

def check_recording_backends() -> dict[str, bool]:
    """Check availability of command line recording tools."""
    return {
        "parecord": _command_exists("parecord"),
        "arecord": _command_exists("arecord"),
        "ffmpeg": _command_exists("ffmpeg"),
    }

def get_recording_config(config: dict[str, Any]) -> dict[str, Any]:
    """Extract and normalize recording configuration, ensuring sane defaults."""
    rec_cfg = config.get("recording", {})
    
    backend = str(rec_cfg.get("backend", "auto"))
    output_dir = str(rec_cfg.get("output_dir", "~/.cache/arova"))
    filename_prefix = str(rec_cfg.get("filename_prefix", "voice_command"))
    
    try:
        sample_rate = int(rec_cfg.get("sample_rate", 16000))
    except (ValueError, TypeError):
        sample_rate = 16000
        
    try:
        channels = int(rec_cfg.get("channels", 1))
    except (ValueError, TypeError):
        channels = 1
        
    try:
        duration_seconds = float(rec_cfg.get("duration_seconds", 5.0))
    except (ValueError, TypeError):
        duration_seconds = 5.0
        
    if output_dir:
        output_dir = os.path.expanduser(output_dir)
        
    return {
        "backend": backend,
        "mode": str(rec_cfg.get("mode", "silence")),
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_seconds": duration_seconds,
        "output_dir": output_dir,
        "filename_prefix": filename_prefix,
        "frame_ms": int(rec_cfg.get("frame_ms", 30)),
        "speech_threshold": float(rec_cfg.get("speech_threshold", 150.0)),
        "silence_threshold": float(rec_cfg.get("silence_threshold", 80.0)),
        "silence_duration_ms": int(rec_cfg.get("silence_duration_ms", 800)),
        "min_speech_duration_ms": int(rec_cfg.get("min_speech_duration_ms", 250)),
        "max_duration_seconds": float(rec_cfg.get("max_duration_seconds", 15.0)),
        "start_timeout_seconds": float(rec_cfg.get("start_timeout_seconds", 4.0)),
        "pre_speech_buffer_ms": int(rec_cfg.get("pre_speech_buffer_ms", 300)),
    }

def make_recording_output_path(config: dict[str, Any], output_path: str | None = None) -> str:
    """Generate or normalize the output path for a recording file."""
    if output_path:
        return os.path.abspath(os.path.expanduser(output_path))
        
    rec_cfg = get_recording_config(config)
    output_dir = rec_cfg["output_dir"]
    prefix = rec_cfg["filename_prefix"]
    
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}-{timestamp}.wav"
    
    return os.path.join(output_dir, filename)

def is_valid_recording_file(path: str) -> bool:
    """Validate that the recorded file exists and isn't just an empty header."""
    if not os.path.exists(path):
        return False
    size = os.path.getsize(path)
    # A standard bare WAV header is 44 bytes. Anything <= 44 is effectively empty.
    return size > 44

def _cleanup_failed_output(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

def _run_recording_cmd(cmd: list[str], output_path: str, backend_name: str, duration: float) -> dict[str, Any]:
    """Helper to run a recording process for a set duration and validate it."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Sleep for the requested duration to capture audio
        time.sleep(duration)
        
        # Cleanly terminate
        proc.terminate()
        try:
            proc.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            
        if is_valid_recording_file(output_path):
            return {
                "ok": True,
                "backend": backend_name,
                "audio_path": output_path,
                "duration_seconds": duration,
                "error": None
            }
        else:
            _cleanup_failed_output(output_path)
            return {
                "ok": False,
                "backend": backend_name,
                "audio_path": None,
                "duration_seconds": duration,
                "error": "Recorded file was missing or empty."
            }
    except Exception as e:
        _cleanup_failed_output(output_path)
        return {
            "ok": False,
            "backend": backend_name,
            "audio_path": None,
            "duration_seconds": duration,
            "error": str(e)
        }

def pcm16_rms(frame_bytes: bytes) -> float:
    count = len(frame_bytes) // 2
    if count == 0:
        return 0.0
    fmt = f"<{count}h"
    shorts = struct.unpack(fmt, frame_bytes)
    sum_squares = sum(s * s for s in shorts)
    return math.sqrt(sum_squares / count)

def is_speech_frame(rms: float, threshold: float) -> bool:
    return rms >= threshold

def ms_to_frames(duration_ms: int, frame_ms: int) -> int:
    if frame_ms <= 0:
        return 0
    return max(1, duration_ms // frame_ms)

def should_stop_after_silence(
    speech_started: bool,
    silent_frames: int,
    silence_frames_required: int,
    speech_frames: int,
    min_speech_frames: int,
) -> bool:
    if not speech_started:
        return False
    if speech_frames < min_speech_frames:
        return False
    return silent_frames >= silence_frames_required

def record_until_silence(output_path: str, config: dict[str, Any]) -> dict[str, Any]:
    """Record audio using pyaudio until silence is detected."""
    rec_cfg = get_recording_config(config)
    try:
        import pyaudio
    except ImportError:
        return {
            "ok": False,
            "backend": "pyaudio",
            "audio_path": None,
            "duration_seconds": 0.0,
            "error": "pyaudio not installed"
        }
    
    sample_rate = rec_cfg["sample_rate"]
    channels = rec_cfg["channels"]
    frame_ms = rec_cfg["frame_ms"]
    speech_threshold = rec_cfg["speech_threshold"]
    silence_threshold = rec_cfg["silence_threshold"]
    silence_duration_ms = rec_cfg["silence_duration_ms"]
    min_speech_duration_ms = rec_cfg["min_speech_duration_ms"]
    max_duration_seconds = rec_cfg["max_duration_seconds"]
    start_timeout_seconds = rec_cfg["start_timeout_seconds"]
    pre_speech_buffer_ms = rec_cfg["pre_speech_buffer_ms"]
    
    chunk_size = int(sample_rate * (frame_ms / 1000.0))
    
    silence_frames_req = ms_to_frames(silence_duration_ms, frame_ms)
    min_speech_frames_req = ms_to_frames(min_speech_duration_ms, frame_ms)
    pre_speech_frames_req = ms_to_frames(pre_speech_buffer_ms, frame_ms)
    
    p = pyaudio.PyAudio()
    start_time = time.time()
    try:
        stream = None
        for attempt in range(3):
            try:
                stream = p.open(format=pyaudio.paInt16,
                                channels=channels,
                                rate=sample_rate,
                                input=True,
                                frames_per_buffer=chunk_size)
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(0.1)
        
        frames = []
        pre_speech_ring = []
        
        speech_started = False
        silent_frames_count = 0
        speech_frames_count = 0
        total_frames = 0
        
        max_total_frames = int(max_duration_seconds * 1000 / frame_ms)
        timeout_frames = int(start_timeout_seconds * 1000 / frame_ms)
        
        while True:
            data = stream.read(chunk_size, exception_on_overflow=False)
            rms = pcm16_rms(data)
            
            if not speech_started:
                if is_speech_frame(rms, speech_threshold):
                    speech_started = True
                    frames.extend(pre_speech_ring)
                    frames.append(data)
                    speech_frames_count += 1
                else:
                    pre_speech_ring.append(data)
                    if len(pre_speech_ring) > pre_speech_frames_req:
                        pre_speech_ring.pop(0)
                    
                    if total_frames > timeout_frames:
                        return {
                            "ok": False,
                            "backend": "pyaudio",
                            "audio_path": None,
                            "duration_seconds": time.time() - start_time,
                            "error": "No speech detected."
                        }
            else:
                frames.append(data)
                if is_speech_frame(rms, speech_threshold):
                    speech_frames_count += 1
                    silent_frames_count = 0
                else:
                    if rms < silence_threshold:
                        silent_frames_count += 1
                    
                if should_stop_after_silence(speech_started, silent_frames_count, silence_frames_req, speech_frames_count, min_speech_frames_req):
                    break
                    
            total_frames += 1
            if total_frames >= max_total_frames:
                break
                
        # Write WAV
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        wf = wave.open(output_path, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        duration = (len(frames) * chunk_size) / sample_rate
        
        if is_valid_recording_file(output_path):
            return {
                "ok": True,
                "backend": "pyaudio",
                "audio_path": output_path,
                "duration_seconds": duration,
                "error": None
            }
        else:
            return {
                "ok": False,
                "backend": "pyaudio",
                "audio_path": None,
                "duration_seconds": duration,
                "error": "Recorded file was missing or empty."
            }
            
    except Exception as e:
        return {
            "ok": False,
            "backend": "pyaudio",
            "audio_path": None,
            "duration_seconds": time.time() - start_time,
            "error": str(e)
        }
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        p.terminate()

def record_with_parecord(output_path: str, config: dict[str, Any], duration: float | None = None) -> dict[str, Any]:
    """Record audio using PulseAudio's parecord command."""
    if not _command_exists("parecord"):
        return {
            "ok": False,
            "backend": "parecord",
            "audio_path": None,
            "duration_seconds": 0.0,
            "error": "Command 'parecord' not found."
        }
        
    rec_cfg = get_recording_config(config)
    dur = duration if duration is not None else rec_cfg["duration_seconds"]
    
    cmd = [
        "parecord",
        "--format=s16le",
        f"--rate={rec_cfg['sample_rate']}",
        f"--channels={rec_cfg['channels']}",
        output_path
    ]
    
    return _run_recording_cmd(cmd, output_path, "parecord", dur)

def record_with_arecord(output_path: str, config: dict[str, Any], duration: float | None = None) -> dict[str, Any]:
    """Record audio using ALSA's arecord command."""
    if not _command_exists("arecord"):
        return {
            "ok": False,
            "backend": "arecord",
            "audio_path": None,
            "duration_seconds": 0.0,
            "error": "Command 'arecord' not found."
        }
        
    rec_cfg = get_recording_config(config)
    dur = duration if duration is not None else rec_cfg["duration_seconds"]
    
    cmd = [
        "arecord",
        "-f", "S16_LE",
        "-c", str(rec_cfg["channels"]),
        "-r", str(rec_cfg["sample_rate"]),
        "-t", "wav",
        output_path
    ]
    
    return _run_recording_cmd(cmd, output_path, "arecord", dur)

def record_with_ffmpeg(output_path: str, config: dict[str, Any], duration: float | None = None) -> dict[str, Any]:
    """Record audio using ffmpeg (pulse interface) as a fallback."""
    if not _command_exists("ffmpeg"):
        return {
            "ok": False,
            "backend": "ffmpeg",
            "audio_path": None,
            "duration_seconds": 0.0,
            "error": "Command 'ffmpeg' not found."
        }
        
    rec_cfg = get_recording_config(config)
    dur = duration if duration is not None else rec_cfg["duration_seconds"]
    
    # Try using pulse for ffmpeg fallback as it's the most universal Linux audio server atm
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "pulse",
        "-i", "default",
        "-ac", str(rec_cfg["channels"]),
        "-ar", str(rec_cfg["sample_rate"]),
        output_path
    ]
    
    return _run_recording_cmd(cmd, output_path, "ffmpeg", dur)

def record_audio(config: dict[str, Any], output_path: str | None = None, duration: float | None = None) -> dict[str, Any]:
    """Top-level function to record audio, routing to the best available backend."""
    rec_cfg = get_recording_config(config)
    backend_choice = rec_cfg["backend"]
    mode = rec_cfg["mode"]
    
    actual_output_path = make_recording_output_path(config, output_path)
    dur = duration if duration is not None else rec_cfg["duration_seconds"]
    
    backends = check_recording_backends()
    
    if mode == "silence":
        res = record_until_silence(actual_output_path, config)
        if res["ok"] or res.get("error") == "No speech detected.":
            return res
        # If it failed for other reasons (e.g. pyaudio missing), fallback
    
    if backend_choice != "auto":
        if backend_choice == "parecord":
            return record_with_parecord(actual_output_path, config, dur)
        elif backend_choice == "arecord":
            return record_with_arecord(actual_output_path, config, dur)
        elif backend_choice == "ffmpeg":
            return record_with_ffmpeg(actual_output_path, config, dur)
        else:
            return {
                "ok": False,
                "backend": backend_choice,
                "audio_path": None,
                "duration_seconds": dur,
                "error": f"Unknown backend: {backend_choice}"
            }
            
    # Auto fallback
    if backends.get("parecord"):
        res = record_with_parecord(actual_output_path, config, dur)
        if res["ok"]: return res
        
    if backends.get("arecord"):
        res = record_with_arecord(actual_output_path, config, dur)
        if res["ok"]: return res
        
    if backends.get("ffmpeg"):
        res = record_with_ffmpeg(actual_output_path, config, dur)
        if res["ok"]: return res
        
    return {
        "ok": False,
        "backend": "auto",
        "audio_path": None,
        "duration_seconds": dur,
        "error": "No working recording backends found."
    }
