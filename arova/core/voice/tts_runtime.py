from typing import Any
import threading
import queue
import logging
import concurrent.futures
from arova.core.events import RuntimeEventBus
from arova.core.voice.cancellation import RuntimeCancellationService
from arova.core.voice.audio_session import AudioSessionManager

import re

def _sanitize_text_for_speech(text: str) -> str:
    """
    Dynamically strips and normalizes URLs, markdown links, code blocks,
    and formatting into natural spoken English for TTS.
    """
    if not text:
        return ""
    
    # 1. Convert markdown links [Label](url) -> Label
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # 2. Strip markdown image links ![Alt](url) -> ""
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)
    
    # 3. Clean raw URLs (https://... or http://...) into natural domain names or clean reference
    def _url_replacer(match):
        url = match.group(0)
        if "music.youtube" in url:
            return "YouTube Music"
        elif "youtube.com" in url or "youtu.be" in url:
            return "YouTube"
        elif "github.com" in url:
            return "GitHub"
        elif "google.com" in url:
            return "Google"
        elif "spotify.com" in url:
            return "Spotify"
        m = re.search(r'https?://(?:www\.)?([^/]+)', url)
        return m.group(1) if m else ""
    
    text = re.sub(r'https?://\S+', _url_replacer, text)
    
    # 4. Strip code fences ```...``` and inline code `code`
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # 5. Strip markdown bold / italic / strikethrough
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    
    # 6. Strip markdown headers, bullets, and table markers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|.*\|', '', text)
    
    # 7. Normalize excess whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _get_field(payload: Any, key: str, default: Any = None) -> Any:
    if isinstance(payload, dict):
        return payload.get(key, default)
    if hasattr(payload, 'data') and isinstance(payload.data, dict):
        val = payload.data.get(key)
        if val is not None:
            return val
    if hasattr(payload, key):
        return getattr(payload, key)
    return default

class TTSRuntime:
    """
    Handles streaming text-to-speech with a pipelined architecture:
    - Synthesis threads pre-render text chunks to audio files in parallel
    - A single playback thread consumes rendered files in strict order
    This eliminates inter-chunk silence gaps.
    """
    
    def __init__(self, event_bus: RuntimeEventBus, config: dict, 
                 cancellation: RuntimeCancellationService, 
                 audio_manager: AudioSessionManager):
        self._event_bus = event_bus
        self._config = config
        self._cancellation = cancellation
        self._audio_manager = audio_manager
        
        # Synthesis thread pool (pre-render up to 3 chunks ahead)
        self._synth_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="TTSSynth")
        
        # Per-turn state
        self._active_turn_id = None
        self._playback_queue = None  # queue of (order_index, audio_path)
        self._playback_thread = None
        self._cancel_token = None
        self._chunk_counter = 0
        self._pending_futures = {}  # order_index -> Future
        self._lock = threading.RLock()
        
        self._event_bus.subscribe("voice", "TEXT_CHUNK_GENERATED", self._on_text_chunk)
        self._event_bus.subscribe("voice", "TEXT_RESPONSE_GENERATED", self._on_text_response)
        self._event_bus.subscribe("runtime", "INTERRUPT_REQUESTED", self._on_interrupt)

    def _ensure_turn(self, turn_id: str):
        """Initialize pipeline for a new turn if needed."""
        with self._lock:
            if self._active_turn_id == turn_id:
                return
            
            # Clean up any previous turn
            self._cleanup_turn()
            
            self._active_turn_id = turn_id
            self._playback_queue = queue.Queue()
            self._chunk_counter = 0
            self._pending_futures = {}
            self._cancel_token = self._cancellation.create_token(f"tts_{turn_id}")
            
            # Start playback consumer thread
            self._playback_thread = threading.Thread(
                target=self._playback_worker, 
                args=(turn_id, self._cancel_token),
                daemon=True, 
                name=f"TTSPlayback-{turn_id[:8]}"
            )
            self._playback_thread.start()
            self._event_bus.emit("voice", "TTS_STARTED", {"turn_id": turn_id})
            logging.info(f"TTSRuntime: Pipeline started for turn {turn_id[:8]}")

    def _synthesize_chunk(self, text: str, order_index: int, turn_id: str, token):
        """Runs in thread pool: synthesize text to an audio file."""
        if token.is_cancelled:
            return None

        # Dynamically sanitize URLs, markdown links, code blocks, and formatting for natural speech
        spoken_text = _sanitize_text_for_speech(text)
        if not spoken_text.strip():
            # If chunk became empty (e.g. was pure URL/markdown syntax), push None to preserve chunk ordering
            if not token.is_cancelled:
                self._playback_queue.put((order_index, None))
            return None
            
        from arova.core.tts import synthesize_with_edge, synthesize_with_piper, detect_language_from_text
        
        lang = detect_language_from_text(spoken_text)
        tts_cfg = self._config.get("tts", {})
        engine_order = tts_cfg.get("engine_order", ["edge", "piper"])
        
        result = None
        for engine in engine_order:
            if token.is_cancelled:
                return None
            if engine == "edge":
                result = synthesize_with_edge(spoken_text, self._config, lang)
            elif engine == "piper":
                result = synthesize_with_piper(spoken_text, self._config, lang)
            if result and result.get("ok"):
                break
        
        if not result or not result.get("ok"):
            logging.warning(f"TTSRuntime: Synthesis failed for chunk #{order_index}: {result.get('error') if result else 'no engine'}")
            if not token.is_cancelled:
                self._playback_queue.put((order_index, None))
            return None
            
        audio_path = result["audio_path"]
        # NOTE: No leading silence padding for streamed chunks — it causes inter-chunk gaps
        
        # Push to playback queue in order
        if not token.is_cancelled:
            self._playback_queue.put((order_index, audio_path))
            
        return audio_path

    def _playback_worker(self, turn_id: str, token):
        """Consumer thread: plays audio files in strict submission order."""
        next_expected = 0
        buffer = {}  # out-of-order buffer: order_index -> audio_path
        eof_received = False
        total_chunks_expected = -1
        
        while not token.is_cancelled:
            # If EOF was received and we've played all expected chunks, we are done
            if eof_received and next_expected >= total_chunks_expected:
                break
                
            try:
                item = self._playback_queue.get(timeout=0.1)
            except queue.Empty:
                continue
                
            if item is None:
                continue
                
            order_index, data = item
            
            if order_index == -1:
                # EOF marker. data contains total_chunks_expected
                eof_received = True
                total_chunks_expected = data
                # Re-check condition immediately
                if next_expected >= total_chunks_expected:
                    break
                continue
            
            # Normal chunk. data is audio_path
            buffer[order_index] = data
            
            # Play all consecutive ready chunks
            while next_expected in buffer:
                path = buffer.pop(next_expected)
                if path and not token.is_cancelled:
                    self._play_file(path, token)
                next_expected += 1
        
        # Cleanup
        self._cancellation.remove_token(f"tts_{turn_id}")
        with self._lock:
            if self._active_turn_id == turn_id:
                self._active_turn_id = None
                self._playback_queue = None
                self._playback_thread = None
        self._event_bus.emit("voice", "TTS_COMPLETED", {"turn_id": turn_id})
        logging.info(f"TTSRuntime: Playback complete for turn {turn_id[:8]}")

    def _play_file(self, audio_path: str, token):
        """Play a single audio file through the audio session manager."""
        import os
        import time
        if token.is_cancelled:
            return
        try:
            self._audio_manager.request_playback(audio_path, priority=30)
            # Wait for playback to finish
            while self._audio_manager._active_playback_pid is not None and not token.is_cancelled:
                time.sleep(0.05)
        except Exception as e:
            logging.error(f"TTSRuntime: Playback error: {e}")
        finally:
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except OSError:
                pass

    def _on_text_chunk(self, payload):
        text = _get_field(payload, "text", "")
        turn_id = _get_field(payload, "turn_id", None) or "unknown_turn"
        vocalize = _get_field(payload, "vocalize", True)
        
        if not vocalize:
            return
            
        if not text.strip():
            return
        
        self._ensure_turn(turn_id)
        
        token = self._cancel_token
        if token and token.is_cancelled:
            return
            
        with self._lock:
            order_index = self._chunk_counter
            self._chunk_counter += 1
        
        # Submit synthesis to thread pool (runs in parallel with playback)
        fut = self._synth_pool.submit(self._synthesize_chunk, text, order_index, turn_id, token)
        self._pending_futures[order_index] = fut
        
    def _on_text_response(self, payload):
        turn_id = _get_field(payload, "turn_id", None) or "unknown_turn"
        text = _get_field(payload, "text", "")
        vocalize = _get_field(payload, "vocalize", True)
        
        if not vocalize:
            # Fake an empty EOF so TTS worker exits immediately without waiting
            with self._lock:
                if self._active_turn_id == turn_id and self._playback_queue is not None:
                    self._playback_queue.put((-1, 0))
            return
            
        if self._playback_queue is not None:
            # Stream mode: send EOF sentinel with total chunks expected
            with self._lock:
                total_chunks = self._chunk_counter
            self._playback_queue.put((-1, total_chunks))
        elif text.strip():
            # Non-streamed full response fallback
            self._ensure_turn(turn_id)
            token = self._cancel_token
            if token and not token.is_cancelled:
                self._synth_pool.submit(self._synthesize_chunk, text, 0, turn_id, token)
                import time
                time.sleep(0.1)
                if self._playback_queue:
                    self._playback_queue.put((-1, 1))
        
    def _on_interrupt(self, payload):
        """Preemptively hard-stop all TTS playback instantly."""
        self._audio_manager.preemptive_stop()
        turn_id = self._active_turn_id
        self._cleanup_turn()
        if turn_id:
            self._event_bus.emit("voice", "TTS_INTERRUPTED", {"turn_id": turn_id})
    
    def _cleanup_turn(self):
        """Cancel and drain any active turn pipeline."""
        with self._lock:
            if self._active_turn_id and self._cancel_token:
                self._cancel_token.cancel()
                self._cancellation.remove_token(f"tts_{self._active_turn_id}")
            for fut in self._pending_futures.values():
                fut.cancel()
            self._pending_futures.clear()
