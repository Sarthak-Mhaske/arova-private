import logging
import threading

class EmbeddingEngine:
    """
    Wraps sentence-transformers for local encoding.
    Loads the model lazily on the first request to avoid slowing down boot time.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()
        
    def _load_model(self):
        if self._model is None:
            logging.info(f"Loading embedding model: {self.model_name}")
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                logging.info("Embedding model loaded.")
            except ImportError:
                logging.error("Failed to import sentence-transformers. Memory embeddings will fail.")
                raise
                
    def encode(self, text: str) -> list[float]:
        with self._lock:
            self._load_model()
            
        if self._model:
            # We use float() to ensure it's a standard python list of floats, not a numpy array,
            # as qdrant-client expects native python types or specific arrays.
            vector = self._model.encode(text)
            return vector.tolist()
        return []
