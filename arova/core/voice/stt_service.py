import logging
import threading
import numpy as np
from typing import Optional
from faster_whisper import WhisperModel
from arova.core.events import RuntimeEventBus
from arova.core.voice.audio_session import AudioSessionManager
from arova.core.time import RuntimeClock

class STTRuntimeService:
    """
    Handles local Speech-to-Text using faster-whisper.
    Buffers audio from Wake to Turn Finalization, then transcribes.
    """
    def __init__(self, event_bus: RuntimeEventBus, audio_session: AudioSessionManager, session=None):
        self._event_bus = event_bus
        self._audio_session = audio_session
        self._session = session
        self._lock = threading.RLock()
        
        self._is_buffering = False
        self._audio_buffer = bytearray()
        self._current_turn_id: str = None  # Captured at wake time
        
        # Lazy load model
        self._model: Optional[WhisperModel] = None
        self._model_size = "tiny.en" # Use tiny.en for ultra-fast TTFP
        
        # Subscriptions
        self._event_bus.subscribe("voice", "WAKE_DETECTED", self._on_wake)
        self._event_bus.subscribe("voice", "FINALIZE_TURN", self._on_finalize)
        self._event_bus.subscribe("runtime", "INTERRUPT_REQUESTED", self._on_interrupt)

    def _ensure_model(self):
        if self._model is None:
            logging.info("Loading faster-whisper model...")
            self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
            logging.info("faster-whisper loaded.")

    def _on_wake(self, payload):
        with self._lock:
            if not self._is_buffering:
                self._is_buffering = True
                self._audio_buffer.clear()
                # Capture turn_id NOW before it can change
                self._current_turn_id = self._session.get_authoritative_turn_id() if self._session else None
                self._audio_session.microphone.subscribe("stt_service", 45, self._process_audio_chunk)
                logging.info(f"STTRuntimeService started buffering. turn_id={self._current_turn_id}")

    def _on_interrupt(self, payload):
        with self._lock:
            self._is_buffering = False
            self._audio_buffer.clear()
            self._audio_session.microphone.unsubscribe("stt_service")
            logging.info("STTRuntimeService interrupted. Buffer cleared.")

    def _on_finalize(self, payload):
        with self._lock:
            if not self._is_buffering:
                return
            self._is_buffering = False
            self._audio_session.microphone.unsubscribe("stt_service")
            
            # Copy buffer and turn_id for async processing
            audio_bytes = bytes(self._audio_buffer)
            turn_id = self._current_turn_id
            self._audio_buffer.clear()
            self._current_turn_id = None
            
            # Offload to thread to not block event bus
            threading.Thread(target=self._transcribe, args=(audio_bytes, turn_id), daemon=True).start()

    def _process_audio_chunk(self, chunk: bytes, sample_rate: int):
        with self._lock:
            if self._is_buffering:
                self._audio_buffer.extend(chunk)

    def _transcribe(self, audio_bytes: bytes, turn_id: str):
        if len(audio_bytes) < 32000:  # Less than 1 second at 16kHz int16
            logging.warning("Audio buffer too short for STT, ignoring.")
            return

        try:
            self._ensure_model()
            
            # Convert to numpy float32 as expected by faster-whisper
            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            
            segments, info = self._model.transcribe(audio_np, beam_size=5)
            
            transcript = " ".join([segment.text for segment in segments]).strip()
            
            if transcript:
                logging.info(f"STT Transcript: {transcript} (turn_id={turn_id})")
                self._event_bus.emit("voice", "TRANSCRIPT_FINAL", {
                    "transcript": transcript,
                    "confidence": 1.0,
                    "timestamp": RuntimeClock.now(),
                    "turn_id": turn_id
                })
            else:
                logging.info("STT Transcript was empty.")
                self._event_bus.emit("runtime", "INTERRUPT_REQUESTED", {"source": "stt_empty"})

        except Exception as e:
            logging.error(f"STT Transcription failed: {e}")
            self._event_bus.emit("runtime", "INTERRUPT_REQUESTED", {"source": "stt_error"})
