import time
import re
from typing import Callable, Awaitable

class AsyncDeltaBuffer:
    """
    Batches incoming LLM tokens and flushes them on complete, natural linguistic boundaries:
    1. Eager first chunk: Flushes chunk #1 immediately on the first complete clause (2-3 words or punctuation)
       so TTS audio starts playback in sub-100ms.
    2. Subsequent chunks: Flushes on natural sentence/clause boundaries (6-10 complete words)
       WITHOUT EVER splitting words, sub-tokens, or Devanagari matras in half.
    """
    def __init__(self, callback: Callable[[str, int], Awaitable[None]], flush_interval_s: float = 0.3):
        self._callback = callback
        self._flush_interval_s = flush_interval_s
        self._buffer = []
        self._last_flush_time = time.time()
        self._seq = 0
        # Punctuation regex includes ASCII and Devanagari danda (।)
        self._punct_regex = re.compile(r'([,.?!;:\u0964]\s+|\n)')

    async def append(self, token: str):
        self._buffer.append(token)
        text = "".join(self._buffer)
        
        has_punct = bool(self._punct_regex.search(text))
        words = text.strip().split()
        
        # ── FAST-PATH FOR FIRST CHUNK (seq == 0) ──
        if self._seq == 0:
            # Flush immediately on first 2-3 complete words (only when token ends with space/punct) or punctuation
            if (len(words) >= 2 and (token.endswith(" ") or token.endswith("\n"))) or has_punct:
                await self.flush()
                return

        # ── SUBSEQUENT CHUNKS (seq >= 1) ──
        # 1. Flush on full sentence termination (. ? ! ।)
        sentence_end = bool(re.search(r'[.?!;\u0964]\s*$', text.strip()))
        if sentence_end and len(words) >= 4:
            await self.flush()
            return
            
        # 2. Flush on mid-sized phrase boundary (8+ words at a complete word boundary)
        if len(words) >= 8 and (token.endswith(" ") or token.endswith("\n") or has_punct):
            await self.flush()
            return

        # 3. Flush if time interval exceeded AND at least 6 complete words
        if (time.time() - self._last_flush_time >= self._flush_interval_s) and len(words) >= 6 and (token.endswith(" ") or token.endswith("\n")):
            await self.flush()

    async def flush(self):
        if not self._buffer:
            return
        
        text = "".join(self._buffer).strip()
        self._buffer.clear()
        self._last_flush_time = time.time()
        
        if text:
            self._seq += 1
            await self._callback(text, self._seq)

    async def close(self):
        await self.flush()
