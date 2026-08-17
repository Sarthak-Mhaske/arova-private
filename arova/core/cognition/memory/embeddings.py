import logging
import threading
import hashlib

class EmbeddingEngine:
    """
    Wraps sentence-transformers for local encoding.
    Loads the model lazily on the first request to avoid slowing down boot time.
    Falls back to deterministic hash embedding when sentence-transformers not available
    — keeps vector pipeline functional in minimal/test envs without heavy torch deps.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()
        self._use_fallback = False
        
    def _load_model(self):
        if self._model is None and not self._use_fallback:
            logging.info(f"Loading embedding model: {self.model_name}")
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logging.info("Embedding model loaded.")
            except ImportError:
                logging.warning("sentence-transformers not installed -- using deterministic hash fallback (384-dim). Install sentence-transformers for true semantic embeddings.")
                self._use_fallback = True
            except Exception as e:
                logging.warning(f"Embedding model load failed ({e}) -- using hash fallback")
                self._use_fallback = True
                
    def _hash_encode(self, text: str) -> list[float]:
        """Word-level hash fallback: sum of word hashes, so 'dark mode' is close to 'prefers dark mode'."""
        import math
        words = text.lower().split()
        if not words:
            words = [text.lower()]
        vec = [0.0] * 384
        for word in words:
            h = hashlib.sha256(word.encode('utf-8')).digest()
            for i in range(384):
                b = h[i % len(h)]
                # Word contribution, scaled
                vec[i] += ((b / 127.5) - 1.0) * 0.5
        # Also mix in whole-text hash for uniqueness
        h_full = hashlib.sha256(text.encode('utf-8')).digest()
        for i in range(384):
            vec[i] += ((h_full[i % len(h_full)] / 127.5) - 1.0) * 0.2
        norm = math.sqrt(sum(x*x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def encode(self, text: str) -> list[float]:
        with self._lock:
            self._load_model()
            
        if self._model:
            try:
                vector = self._model.encode(text)
                return vector.tolist()
            except Exception as e:
                logging.warning(f"Embedding encode failed ({e}), using hash fallback")
                return self._hash_encode(text)
        # Fallback path
        return self._hash_encode(text)
