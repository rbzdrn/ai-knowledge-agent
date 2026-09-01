"""
ChromaDB-backed vector store for document embeddings.
"""

import json
from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import config


class VectorStore:
    """Manages document embeddings with ChromaDB."""

    def __init__(self, collection_name: str = "knowledge_base"):
        self.client = chromadb.PersistentClient(
            path=str(config.vectordb_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection_name = collection_name
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.collection = self.client.get_collection(self.collection_name)
        except Exception:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

    def add(
        self,
        doc_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadatas: List[dict],
    ) -> List[str]:
        """Add document chunks to the vector store. Returns chunk IDs."""
        chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        self.collection.add(
            ids=chunk_ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return chunk_ids

    def search(
        self, query_embedding: List[float], top_k: int | None = None, where: Optional[dict] = None
    ) -> List[dict]:
        """Semantic search by embedding vector."""
        top_k = top_k or config.dense_top_k
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                hits.append({
                    "chunk_id": chunk_id,
                    "doc_id": self._extract_doc_id(chunk_id),
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": 1.0 - results["distances"][0][i] if results["distances"] else 0.0,
                })
        return hits

    def get_all_chunks(self) -> List[dict]:
        """Retrieve all chunks (for BM25 indexing)."""
        try:
            result = self.collection.get(include=["documents", "metadatas"])
            chunks = []
            if result["ids"]:
                for i, cid in enumerate(result["ids"]):
                    chunks.append({
                        "chunk_id": cid,
                        "doc_id": self._extract_doc_id(cid),
                        "text": result["documents"][i] if result["documents"] else "",
                        "metadata": result["metadatas"][i] if result["metadatas"] else {},
                    })
            return chunks
        except Exception:
            return []

    def delete_document(self, doc_id: str) -> int:
        """Delete all chunks belonging to a document."""
        try:
            existing = self.collection.get(
                where={"doc_id": doc_id}, include=["metadatas"]
            )
            if existing["ids"]:
                self.collection.delete(ids=existing["ids"])
                return len(existing["ids"])
            return 0
        except Exception:
            return 0

    def list_documents(self) -> List[dict]:
        """List unique documents in the store."""
        try:
            result = self.collection.get(include=["metadatas"])
            seen = {}
            if result["metadatas"]:
                for meta in result["metadatas"]:
                    doc_id = meta.get("doc_id", "")
                    if doc_id and doc_id not in seen:
                        seen[doc_id] = {
                            "doc_id": doc_id,
                            "filename": meta.get("filename", "unknown"),
                            "source": meta.get("source", ""),
                            "file_type": meta.get("file_type", ""),
                            "chunk_count": 1,
                        }
                    elif doc_id in seen:
                        seen[doc_id]["chunk_count"] += 1
            return sorted(seen.values(), key=lambda x: x["filename"])
        except Exception:
            return []

    @staticmethod
    def _extract_doc_id(chunk_id: str) -> str:
        return chunk_id.rsplit("_chunk_", 1)[0]

    def count(self) -> int:
        return self.collection.count()
