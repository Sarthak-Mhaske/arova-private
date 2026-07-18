import time
import re
from typing import Callable, Awaitable

class AsyncDeltaBuffer:
    """
    Batches incoming LLM tokens and flushes them based on either:
    1. A time interval (e.g. 50ms) to prevent render storms
    2. Punctuation boundaries to preserve natural TTS conversational pacing
    """
    def __init__(self, callback: Callable[[str, int], Awaitable[None]], flush_interval_s: float = 0.05):
        self._callback = callback
        self._flush_interval_s = flush_interval_s
        self._buffer = []
        self._last_flush_time = time.time()
        self._seq = 0
        # Flush on sentence-ending punctuation or newlines
        self._punctuation_pattern = re.compile(r'([.?!]\s+|[.?!]$|\n)')

    async def append(self, token: str):
        self._buffer.append(token)
        
        # Flush if we hit a punctuation boundary
        if self._punctuation_pattern.search(token):
            await self.flush()
            return
            
        # Flush if we exceed the interval
        if time.time() - self._last_flush_time >= self._flush_interval_s:
            await self.flush()

    async def flush(self):
        if not self._buffer:
            return
        
        text = "".join(self._buffer)
        self._buffer.clear()
        self._last_flush_time = time.time()
        
        self._seq += 1
        await self._callback(text, self._seq)

    async def close(self):
        await self.flush()
