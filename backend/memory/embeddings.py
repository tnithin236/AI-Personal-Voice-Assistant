"""all-MiniLM-L6-v2 embeddings, CPU only, loaded on first use."""
import logging
import threading
from pathlib import Path

log = logging.getLogger(__name__)
DIM = 384


class Embedder:
    def __init__(self, model_name: str, cache_dir: Path):
        self.model_name, self.cache_dir = model_name, cache_dir
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer
                log.info("Loading embedding model %s (CPU)...", self.model_name)
                self._model = SentenceTransformer(self.model_name, device="cpu",
                                                  cache_folder=str(self.cache_dir / "embeddings"))
        return self._model

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        with self._lock:  # SentenceTransformer is not guaranteed thread-safe
            vecs = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        return vecs.tolist()
