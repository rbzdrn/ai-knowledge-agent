"""
Hybrid retrieval: combines dense (vector similarity) and sparse (BM25) search
with Reciprocal Rank Fusion (RRF).
"""

import re
from typing import List, Dict, Optional

import numpy as np

from ..config import config
from ..vectordb.store import VectorStore


class BM25Scorer:
    """Minimal BM25 implementation for sparse retrieval."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: List[str] = []
        self.doc_freq: Dict[str, int] = {}
        self.avgdl: float = 0
        self._initialized = False

    def index(self, chunks: List[dict]):
        """Build BM25 index from chunk dicts with 'text' keys."""
        self.corpus = [c["text"] for c in chunks]
        self._chunk_meta = chunks
        total_length = 0
        for text in self.corpus:
            tokens = self._tokenize(text)
            total_length += len(tokens)
            seen = set()
            for token in tokens:
                if token not in seen:
                    self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
                    seen.add(token)
        self.avgdl = total_length / max(len(self.corpus), 1)
        self.N = len(self.corpus)
        self._initialized = True

    def search(self, query: str, top_k: int = 10) -> List[dict]:
        """BM25 search, returns scored hits."""
        if not self._initialized:
            return []
        query_tokens = self._tokenize(query)
        scores = []
        for idx, text in enumerate(self.corpus):
            score = self._score(query_tokens, text, idx)
            if score > 0:
                scores.append((idx, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scores[:top_k]:
            meta = self._chunk_meta[idx]
            results.append({
                "chunk_id": meta.get("chunk_id", ""),
                "doc_id": meta.get("doc_id", ""),
                "text": meta["text"],
                "metadata": meta.get("metadata", {}),
                "score": score,
            })
        return results

    def _score(self, query_tokens: List[str], doc_text: str, doc_idx: int) -> float:
        doc_tokens = self._tokenize(doc_text)
        doc_len = len(doc_tokens)
        if doc_len == 0:
            return 0.0
        tf = {}
        for t in doc_tokens:
            tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for token in query_tokens:
            if token not in self.doc_freq:
                continue
            df = self.doc_freq[token]
            idf = np.log(1.0 + (self.N - df + 0.5) / (df + 0.5))
            t = tf.get(token, 0)
            numerator = t * (self.k1 + 1)
            denominator = t + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            score += idf * numerator / denominator
        return score

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # CJK-aware tokenization: split on non-alphanumeric, keep CJK chars separate
        text = text.lower()
        tokens = []
        for char in text:
            if char.isalnum() or '一' <= char <= '鿿' or '぀' <= char <= 'ヿ':
                tokens.append(char)
            elif char.isspace():
                tokens.append(char)
        joined = "".join(tokens)
        return [t for t in re.split(r'\s+', joined) if t and len(t) > 1]


class HybridRetriever:
    """Combines dense (vector) and sparse (BM25) retrieval with RRF fusion."""

    def __init__(self, vector_store: VectorStore, embedder):
        self.vs = vector_store
        self.embedder = embedder
        self.bm25 = BM25Scorer()
        self._bm25_ready = False

    def build_bm25_index(self):
        """(Re)build the BM25 index from all chunks in the vector store."""
        chunks = self.vs.get_all_chunks()
        if chunks:
            self.bm25.index(chunks)
            self._bm25_ready = True

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        doc_ids: Optional[List[str]] = None,
    ) -> List[dict]:
        """Hybrid retrieval with RRF fusion."""
        top_k = top_k or config.hybrid_top_k

        # Dense retrieval
        query_emb = self.embedder.embed(query)
        where = {"doc_id": {"$in": doc_ids}} if doc_ids else None
        dense_results = self.vs.search(query_emb, top_k=config.dense_top_k, where=where)

        # Sparse retrieval
        sparse_results = self.bm25.search(query, top_k=config.sparse_top_k)
        if doc_ids:
            sparse_results = [r for r in sparse_results if r["doc_id"] in doc_ids]

        # Reciprocal Rank Fusion
        fused = self._rrf_fusion(dense_results, sparse_results, k=60)
        fused = fused[:top_k]

        return fused

    def _rrf_fusion(
        self, dense: List[dict], sparse: List[dict], k: int = 60
    ) -> List[dict]:
        scores: Dict[str, float] = {}
        docs: Dict[str, dict] = {}

        for rank, hit in enumerate(dense):
            cid = hit["chunk_id"]
            scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
            docs[cid] = hit
            docs[cid]["source"] = "dense"

        for rank, hit in enumerate(sparse):
            cid = hit["chunk_id"]
            scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
            if cid not in docs:
                docs[cid] = hit
                docs[cid]["source"] = "sparse"
            else:
                docs[cid]["source"] = "both"

        sorted_ids = sorted(scores, key=scores.get, reverse=True)
        results = []
        for cid in sorted_ids:
            entry = dict(docs[cid])
            entry["rrf_score"] = round(scores[cid], 6)
            results.append(entry)
        return results
