"""
CJK-aware Recursive Character Text Splitter.
"""

import re
from typing import List, Tuple

from ..config import config


class TextChunker:
    """Split text into overlapping chunks for embedding and retrieval."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.chunk_size = chunk_size or config.chunk_size
        self.chunk_overlap = chunk_overlap or config.chunk_overlap
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

        self._separators = [
            "\n\n", "\n", "。", ". ", ".", "；", ";", "！", "!", "？", "?", " ", ""
        ]

    def split(self, text: str) -> List[str]:
        return self._split_recursive(text, self._separators)

    def split_with_metadata(self, text: str, base_metadata: dict) -> List[dict]:
        """Split and return chunks with per-chunk metadata."""
        chunks = self.split(text)
        results = []
        for i, chunk in enumerate(chunks):
            meta = dict(base_metadata)
            meta["chunk_index"] = i
            meta["chunk_count"] = len(chunks)
            results.append({"text": chunk, "metadata": meta})
        return results

    def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
        chunks = []
        separator = separators[0]
        next_separators = separators[1:] if len(separators) > 1 else [""]

        if not separator:
            # Final fallback: split by fixed chunk_size
            return self._split_by_length(text)

        splits = text.split(separator)
        current = ""
        for part in splits:
            candidate = current + (separator if current else "") + part
            if len(candidate) <= self.chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                if len(part) > self.chunk_size:
                    sub_chunks = self._split_recursive(part, next_separators)
                    if chunks and self.chunk_overlap > 0:
                        last = chunks[-1]
                        overlap_text = last[-self.chunk_overlap:]
                        if sub_chunks:
                            sub_chunks[0] = overlap_text + sub_chunks[0]
                    chunks.extend(sub_chunks)
                    current = ""
                else:
                    current = part

        if current.strip():
            chunks.append(current.strip())

        # Merge short chunks
        return self._merge_short(chunks)

    def _split_by_length(self, text: str) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end].strip())
            start = end - self.chunk_overlap
            if start >= len(text):
                break
            if start < 0:
                start = 0
        return [c for c in chunks if c]

    def _merge_short(self, chunks: List[str], min_len: int = 50) -> List[str]:
        if not chunks:
            return chunks
        merged = []
        buffer = ""
        for chunk in chunks:
            if len(chunk) < min_len and merged:
                merged[-1] = merged[-1] + " " + chunk
            else:
                merged.append(chunk)
        return merged