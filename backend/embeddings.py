"""
Embedding generator using sentence-transformers.
First run will download ~80MB model from HuggingFace.
If blocked by SSL/proxy, set HF_ENDPOINT=https://hf-mirror.com for mirror access.
"""

import os
from typing import List

from .config import config


class Embedder:
    """Generate embeddings using local sentence-transformers model."""

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or config.embedding_model
        self.device = device or config.embedding_device
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            kwargs = {"device": self.device}
            # Try local-only first (avoid SSL issues if model is cached)
            try:
                self._model = SentenceTransformer(
                    self.model_name, local_files_only=True, **kwargs
                )
            except Exception:
                # Auto-configure mirror for users in China
                if not os.environ.get("HF_ENDPOINT"):
                    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
                print(f"Downloading embedding model '{self.model_name}' (one-time, ~80MB)...")
                self._model = SentenceTransformer(self.model_name, **kwargs)
        return self._model

    def embed(self, text: str) -> List[float]:
        return self.model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return embeddings.tolist()

    @property
    def dim(self) -> int:
        return self.model.get_sentence_embedding_dimension()
