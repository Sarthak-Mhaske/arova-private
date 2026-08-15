"""
VoiceConversationLoop — Unified, real-time voice conversation engine.

Features:
  - Real-time partial transcription (words appear live on UI as user speaks)
  - Dual-gate VAD + Energy noise baseline (prevents fan/ambient noise from preventing auto-silence)
  - Snappy auto-turn finalization (1.14s consecutive silence automatically triggers transcription & LLM)
  - Pre-allocated 30s ring buffer
  - Eager whisper model preload
"""

import logging
import threading
import time
import numpy as np
from enum import Enum, auto
from typing import Any, Optional, Callable

try:
    import webrtcvad
except ImportError:
    webrtcvad = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

from arova.core.events import RuntimeEventBus
from arova.core.voice.audio_session import AudioSessionManager
from arova.core.time import RuntimeClock


class LoopState(Enum):
    IDLE = auto()
    LISTENING = auto()      # Mic active, waiting for speech
    RECORDING = auto()      # Speech detected, buffering audio & streaming partials
    TRANSCRIBING = auto()   # Silence detected, running final STT
    RESPONDING = auto()     # LLM + TTS in progress


class VoiceConversationLoop:
    """
    Unified voice conversation engine with real-time partial STT streaming
    and snappy dual-gated silence auto-finalization.
    """

    # ── Configuration ──────────────────────────────────────────────
    SAMPLE_RATE = 16000
    FRAME_BYTES = 480 * 2                 # 30ms at 16kHz, int16 = 960 bytes per frame
    MAX_RECORD_S = 30.0                   # Hard cap on recording duration
    MAX_BUFFER_BYTES = SAMPLE_RATE * 2 * int(MAX_RECORD_S)  # ~960KB ring
    INITIAL_LISTEN_TIMEOUT_S = 12.0       # Max wait for speech start
    POST_SPEECH_SILENCE_S = 0.8           # 800ms post-speech silence window (snappy conversational cutoff)
    CONSECUTIVE_SILENCE_FRAMES_CAP = 25   # 25 * 30ms = 750ms consecutive silence cap
    MIN_SPEECH_FRAMES = 2                 # 2 consecutive speech frames to confirm speech start
    MIN_AUDIO_BYTES_FOR_STT = 8000        # ~0.25s minimum audio to attempt transcription
    PARTIAL_STT_INTERVAL_S = 0.2          # Run partial STT every 200ms for live surface-level typing
    VAD_SENSITIVITY = 3                   # WebRTC VAD aggressiveness (0-3)
    WHISPER_MODEL = "base"                # Multilingual model with high-accuracy Hindi (Devanagari) & English
    WHISPER_BEAM_SIZE = 1                 # Beam size 1 for ultra-fast partial & final STT

    def __init__(self, event_bus: RuntimeEventBus, audio_session: AudioSessionManager, 
                 session: Any, on_mic_state: Optional[Callable[[bool], None]] = None):
        self._event_bus = event_bus
        self._audio_session = audio_session
        self._session = session
        self._on_mic_state = on_mic_state  # Callback to broadcast mic state to UI

        # ── State ──────────────────────────────────────────────────
        self._state = LoopState.IDLE
        self._lock = threading.Lock()

        # ── VAD & Energy Baseline ──────────────────────────────────
        self._vad = webrtcvad.Vad(self.VAD_SENSITIVITY) if webrtcvad else None
        self._noise_floor = 100.0          # Dynamic AC energy baseline

        # ── Audio buffer (pre-allocated) ───────────────────────────
        self._buffer = bytearray(self.MAX_BUFFER_BYTES)
        self._buf_len = 0                   # Actual bytes written this turn

        # ── Speech tracking ────────────────────────────────────────
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._last_speech_time = 0.0
        self._listen_start_time = 0.0
        self._turn_id: Optional[str] = None

        # ── Real-time Partial STT tracking ─────────────────────────
        self._last_partial_time = 0.0
        self._last_partial_text = ""
        self._partial_running = False

        # ── STT model (lazy but eager on first use) ────────────────
        self._stt_model: Optional[Any] = None
        self._model_loading = False
        self._model_lock = threading.Lock()

        # ── Mic subscription tracking ─────────────────────────────
        self._mic_subscribed = False

        # ── Watchdog thread ────────────────────────────────────────
        self._watchdog_active = True
        threading.Thread(target=self._watchdog_loop, daemon=True, name="VoiceLoop-Watchdog").start()

        # ── Subscriptions ──────────────────────────────────────────
        self._event_bus.subscribe("voice", "TTS_COMPLETED", self._on_tts_completed)
        self._event_bus.subscribe("voice", "TTS_INTERRUPTED", self._on_tts_completed)
        self._event_bus.subscribe("runtime", "INTERRUPT_REQUESTED", self._on_interrupt)

        # ── Preload Whisper model in background at startup ─────────
        self._preload_model_async()

        logging.info("VoiceConversationLoop initialized (real-time streaming enabled).")

    # ══════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════

    def start_listening(self):
        """Called when user clicks the mic button (ON)."""
        with self._lock:
            if self._state != LoopState.IDLE:
                logging.warning(f"VoiceLoop: start_listening called in state {self._state.name}, ignoring.")
                return

            # Barge-in: Preemptively hard-stop any active TTS playback instantly
            self._event_bus.emit("runtime", "INTERRUPT_REQUESTED", {"source": "manual_mic_start"})

            self._transition(LoopState.LISTENING)
            self._reset_turn_state()
            self._listen_start_time = RuntimeClock.now()

            # Start a new session turn
            self._session.start_new_turn("")
            self._turn_id = self._session.get_authoritative_turn_id()
            logging.info(f"VoiceLoop: Listening started. turn_id={self._turn_id}")

            # Subscribe to mic audio
            self._subscribe_mic()

            # Preload whisper model in background if not loaded
            self._preload_model_async()

        # Notify UI
        self._broadcast_mic_state(True)

    def stop_listening(self):
        """Called when user clicks the mic button (OFF) — manual stop."""
        with self._lock:
            if self._state == LoopState.IDLE:
                return

            if self._state in (LoopState.LISTENING, LoopState.RECORDING):
                if self._buf_len >= self.MIN_AUDIO_BYTES_FOR_STT and self._state == LoopState.RECORDING:
                    logging.info("VoiceLoop: Manual stop with audio — transcribing immediately.")
                    self._begin_transcription()
                else:
                    logging.info("VoiceLoop: Manual stop with no/insufficient audio — cancelling.")
                    self._cancel_turn()
            elif self._state in (LoopState.TRANSCRIBING, LoopState.RESPONDING):
                logging.info(f"VoiceLoop: Manual stop in {self._state.name}, letting current processing finish.")

    def get_state(self) -> str:
        return self._state.name

    # ══════════════════════════════════════════════════════════════
    # AUDIO CALLBACK (called on sounddevice thread every 30ms)
    # ══════════════════════════════════════════════════════════════

    def _on_audio_chunk(self, chunk: bytes, sample_rate: int):
        state = self._state
        if state not in (LoopState.LISTENING, LoopState.RECORDING):
            return

        # ── Dual VAD + Energy Baseline Evaluation ─────────────────
        is_speech = False
        if len(chunk) == self.FRAME_BYTES:
            audio_np = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            energy = float(np.std(audio_np))

            # Update background noise floor (slow exponential moving average)
            self._noise_floor = 0.96 * self._noise_floor + 0.04 * energy

            vad_speech = False
            if self._vad:
                try:
                    vad_speech = self._vad.is_speech(chunk, sample_rate)
                except Exception:
                    pass

            # True speech requires BOTH VAD detection AND energy above noise threshold
            is_speech = vad_speech and (energy > (self._noise_floor * 1.4 + 80.0))

        now = RuntimeClock.now()

        if state == LoopState.LISTENING:
            if is_speech:
                self._consecutive_speech_frames += 1
                if self._consecutive_speech_frames >= self.MIN_SPEECH_FRAMES:
                    with self._lock:
                        if self._state == LoopState.LISTENING:
                            # Speech barge-in: kill any residual TTS playback
                            self._event_bus.emit("runtime", "INTERRUPT_REQUESTED", {"source": "speech_barge_in"})
                            self._transition(LoopState.RECORDING)
                            self._last_speech_time = now
                            self._consecutive_silence_frames = 0
                            self._last_partial_time = now
                            logging.info("VoiceLoop: Speech detected — recording & live transcription started.")
            else:
                self._consecutive_speech_frames = 0

            # Check initial listening timeout
            if now - self._listen_start_time > self.INITIAL_LISTEN_TIMEOUT_S:
                with self._lock:
                    if self._state == LoopState.LISTENING:
                        logging.info(f"VoiceLoop: No speech detected in {self.INITIAL_LISTEN_TIMEOUT_S}s — cancelling.")
                        self._cancel_turn()
                return

        if state == LoopState.RECORDING or self._state == LoopState.RECORDING:
            # Buffer audio
            chunk_len = len(chunk)
            if self._buf_len + chunk_len <= self.MAX_BUFFER_BYTES:
                self._buffer[self._buf_len:self._buf_len + chunk_len] = chunk
                self._buf_len += chunk_len
            else:
                with self._lock:
                    if self._state == LoopState.RECORDING:
                        logging.info("VoiceLoop: Max recording duration reached (30s) — finalizing.")
                        self._begin_transcription()
                return

            if is_speech:
                self._last_speech_time = now
                self._consecutive_silence_frames = 0
            else:
                self._consecutive_silence_frames += 1

            # Check consecutive silence frames threshold (1.14 seconds)
            if self._consecutive_silence_frames >= self.CONSECUTIVE_SILENCE_FRAMES_CAP:
                with self._lock:
                    if self._state == LoopState.RECORDING:
                        logging.info(f"VoiceLoop: Silence threshold reached ({self._consecutive_silence_frames} frames / 1.14s) — auto-finalizing.")
                        self._begin_transcription()
                return

            # Trigger real-time partial transcription pass every 500ms
            if now - self._last_partial_time >= self.PARTIAL_STT_INTERVAL_S and not self._partial_running:
                self._last_partial_time = now
                self._run_partial_transcription_async()

    # ══════════════════════════════════════════════════════════════
    # WATCHDOG TIMER LOOP (runs in background)
    # ══════════════════════════════════════════════════════════════

    def _watchdog_loop(self):
        while self._watchdog_active:
            time.sleep(0.1)
            if self._state != LoopState.RECORDING:
                continue

            now = RuntimeClock.now()
            with self._lock:
                if self._state == LoopState.RECORDING and self._last_speech_time > 0:
                    silence_duration = now - self._last_speech_time
                    if silence_duration >= self.POST_SPEECH_SILENCE_S:
                        logging.info(f"VoiceLoop: Watchdog triggered silence finalization ({silence_duration:.2f}s).")
                        self._begin_transcription()

    # ══════════════════════════════════════════════════════════════
    # REAL-TIME PARTIAL STT STREAMING
    # ══════════════════════════════════════════════════════════════

    def _run_partial_transcription_async(self):
        if self._buf_len < 8000 or self._stt_model is None:
            return
        self._partial_running = True
        audio_snapshot = bytes(self._buffer[:self._buf_len])
        threading.Thread(
            target=self._partial_transcribe_worker,
            args=(audio_snapshot,),
            daemon=True,
            name="VoiceLoop-PartialSTT"
        ).start()

    def _partial_transcribe_worker(self, audio_bytes: bytes):
        try:
            if self._state != LoopState.RECORDING:
                return

            audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            prompt = "यह हिंदी और अंग्रेजी में बातचीत है। This is a conversation in Hindi and English."
            segments, info = self._stt_model.transcribe(
                audio_np, 
                beam_size=1,
                temperature=0.0,
                initial_prompt=prompt
            )
            if info.language == "ur":
                segments, info = self._stt_model.transcribe(
                    audio_np,
                    beam_size=1,
                    language="hi",
                    temperature=0.0
                )
            text = " ".join(seg.text for seg in segments).strip()

            if text and text != self._last_partial_text and self._state == LoopState.RECORDING:
                self._last_partial_text = text
                logging.debug(f"VoiceLoop partial transcript: '{text}'")
                # Emit partial transcript event for UI live display
                self._event_bus.emit("voice", "PARTIAL_TRANSCRIPT", {
                    "transcript": text,
                    "turn_id": self._turn_id
                })
        except Exception:
            pass
        finally:
            self._partial_running = False

    # ══════════════════════════════════════════════════════════════
    # INTERNAL STATE TRANSITIONS
    # ══════════════════════════════════════════════════════════════

    def _transition(self, new_state: LoopState):
        old = self._state
        self._state = new_state
        if old != new_state:
            logging.info(f"VoiceLoop: {old.name} → {new_state.name}")
            self._event_bus.emit("state", "STATE_CHANGED", {"state": new_state.name.lower()})

    def _reset_turn_state(self):
        self._buf_len = 0
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._last_speech_time = 0.0
        self._last_partial_time = 0.0
        self._last_partial_text = ""
        self._turn_id = None

    def _subscribe_mic(self):
        if not self._mic_subscribed:
            self._audio_session.microphone.subscribe("voice_loop", 50, self._on_audio_chunk)
            self._mic_subscribed = True

    def _unsubscribe_mic(self):
        if self._mic_subscribed:
            self._audio_session.microphone.unsubscribe("voice_loop")
            self._mic_subscribed = False

    def _cancel_turn(self):
        self._unsubscribe_mic()
        if self._turn_id:
            self._session.invalidate_turn()
        self._reset_turn_state()
        self._transition(LoopState.IDLE)
        threading.Thread(target=self._broadcast_mic_state, args=(False,), daemon=True).start()

    def _begin_transcription(self):
        self._unsubscribe_mic()
        self._transition(LoopState.TRANSCRIBING)

        # Notify UI immediately that recording finished (reset mic button to neutral)
        threading.Thread(target=self._broadcast_mic_state, args=(False,), daemon=True).start()

        audio_bytes = bytes(self._buffer[:self._buf_len])
        turn_id = self._turn_id
        buf_len = self._buf_len

        logging.info(f"VoiceLoop: Finalizing {buf_len} bytes ({buf_len / (self.SAMPLE_RATE * 2):.1f}s) for turn {turn_id and turn_id[:8]}")

        threading.Thread(
            target=self._transcribe_and_emit,
            args=(audio_bytes, turn_id),
            daemon=True,
            name=f"VoiceLoop-STT-{turn_id and turn_id[:8]}"
        ).start()

    # ══════════════════════════════════════════════════════════════
    # FINAL TRANSCRIPTION & EMISSION
    # ══════════════════════════════════════════════════════════════

    def _preload_model_async(self):
        if self._stt_model is not None or self._model_loading:
            return
        self._model_loading = True
        threading.Thread(target=self._load_model, daemon=True, name="VoiceLoop-ModelLoad").start()

    def _load_model(self):
        with self._model_lock:
            if self._stt_model is not None:
                self._model_loading = False
                return
            try:
                logging.info(f"VoiceLoop: Loading faster-whisper model '{self.WHISPER_MODEL}'...")
                self._stt_model = WhisperModel(self.WHISPER_MODEL, device="cpu", compute_type="int8")
                logging.info("VoiceLoop: Whisper model loaded.")
            except Exception as e:
                logging.error(f"VoiceLoop: Failed to load whisper model: {e}")
            finally:
                self._model_loading = False

    def _transcribe_and_emit(self, audio_bytes: bytes, turn_id: Optional[str]):
        if len(audio_bytes) < self.MIN_AUDIO_BYTES_FOR_STT:
            logging.warning(f"VoiceLoop: Audio too short ({len(audio_bytes)} bytes), skipping STT.")
            with self._lock:
                self._cancel_turn()
            return

        transcript = ""
        
        # ── 1. Primary: Groq whisper-large-v3-turbo (Cloud Indic STT) ──
        try:
            from arova.core.config.loader import load_config
            from arova.core.stt import transcribe_with_retry_for_indic
            config = getattr(self._session, "config", None) or load_config()
            
            import tempfile, io, wave
            buf = io.BytesIO()
            with wave.open(buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.SAMPLE_RATE)
                wf.writeframes(audio_bytes)
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(buf.getvalue())
                tmp_wav_path = f.name
            
            try:
                res = transcribe_with_retry_for_indic(tmp_wav_path, config)
                if res and res.get("ok") and res.get("text"):
                    transcript = res["text"].strip()
                    logging.info(f"VoiceLoop: Groq large-v3 STT result: \"{transcript}\" (turn_id={turn_id and turn_id[:8]})")
            finally:
                try:
                    import os
                    if os.path.exists(tmp_wav_path):
                        os.remove(tmp_wav_path)
                except Exception:
                    pass
        except Exception as e:
            logging.debug(f"VoiceLoop: Groq cloud STT fallback triggered: {e}")

        # ── 2. Local Fallback: faster-whisper (if offline / no Groq response) ──
        if not transcript:
            try:
                self._load_model()
                if self._stt_model is not None:
                    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    prompt = "यह हिंदी और अंग्रेजी में बातचीत है। This is a conversation in Hindi and English. गाना चलाओ, विंडो बंद करो, play music, open browser."
                    segments, info = self._stt_model.transcribe(
                        audio_np, 
                        beam_size=self.WHISPER_BEAM_SIZE,
                        temperature=0.0,
                        initial_prompt=prompt
                    )
                    if info.language == "ur":
                        logging.info("VoiceLoop: Phonetic Urdu detected, decoding as Hindi (Devanagari)...")
                        segments, info = self._stt_model.transcribe(
                            audio_np,
                            beam_size=self.WHISPER_BEAM_SIZE,
                            language="hi",
                            temperature=0.0
                        )
                    transcript = " ".join(seg.text for seg in segments).strip()
                    logging.info(f"VoiceLoop: Local faster-whisper STT result: \"{transcript}\" (turn_id={turn_id and turn_id[:8]})")
            except Exception as e:
                logging.error(f"VoiceLoop: Local STT failed: {e}")

        if transcript:
            with self._lock:
                self._transition(LoopState.RESPONDING)

            # Broadcast final transcript to EventBus
            self._event_bus.emit("voice", "TRANSCRIPT_FINAL", {
                "transcript": transcript,
                "confidence": 1.0,
                "timestamp": RuntimeClock.now(),
                "turn_id": turn_id
            })
        else:
            logging.info("VoiceLoop: Final STT returned empty transcript.")
            with self._lock:
                self._cancel_turn()

    # ══════════════════════════════════════════════════════════════
    # EVENT HANDLERS & NOTIFICATIONS
    # ══════════════════════════════════════════════════════════════

    def _on_tts_completed(self, payload):
        with self._lock:
            if self._state == LoopState.RESPONDING:
                logging.info("VoiceLoop: Response complete — returning to IDLE.")
                self._reset_turn_state()
                self._transition(LoopState.IDLE)

        self._broadcast_mic_state(False)

    def _on_interrupt(self, payload):
        source = payload.get("source") if isinstance(payload, dict) else getattr(payload, "source", None)
        if source in ("manual_mic_start", "speech_barge_in"):
            return

        with self._lock:
            # Only interrupt the loop if it is currently in RESPONDING state (TTS in progress)
            if self._state not in (LoopState.RESPONDING, LoopState.TRANSCRIBING):
                return
            logging.info(f"VoiceLoop: Interrupt received in state {self._state.name}.")
            self._unsubscribe_mic()
            self._reset_turn_state()
            self._transition(LoopState.IDLE)

        self._broadcast_mic_state(False)

    def _broadcast_mic_state(self, enabled: bool):
        if self._on_mic_state:
            try:
                self._on_mic_state(enabled)
            except Exception as e:
                logging.error(f"VoiceLoop: mic state callback error: {e}")

    def stop(self):
        self._watchdog_active = False
        with self._lock:
            self._unsubscribe_mic()
            self._state = LoopState.IDLE
        logging.info("VoiceConversationLoop stopped.")
