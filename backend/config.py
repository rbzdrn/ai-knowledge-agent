"""
AI Knowledge Base Agent — Configuration
"""

import os
from pathlib import Path
from dataclasses import dataclass, field

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
VECTORDB_DIR = DATA_DIR / "vectordb"
UPLOAD_DIR = DATA_DIR / "uploads"


@dataclass
class Config:
    # Paths
    data_dir: Path = DATA_DIR
    vectordb_dir: Path = VECTORDB_DIR
    upload_dir: Path = UPLOAD_DIR

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    embedding_device: str = "cpu"  # or "cuda"

    # Chunking
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Retrieval
    dense_top_k: int = 10
    sparse_top_k: int = 10
    hybrid_top_k: int = 8
    use_reranker: bool = False  # cross-encoder reranking is slower but more accurate

    # Agent
    llm_model: str = "claude-sonnet-4-6"  # or claude-opus-4-7
    llm_max_tokens: int = 2048
    conversation_ttl: int = 3600  # 1 hour

    # Knowledge Graph
    kg_max_entities_per_chunk: int = 5

    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.vectordb_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @property
    def anthropic_api_key(self) -> str:
        return os.environ.get("ANTHROPIC_API_KEY", "")


config = Config()
