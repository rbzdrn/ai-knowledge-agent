"""
AI Knowledge Base Agent — LLM-agnostic.
"""

import json
from typing import List, Dict, Optional

from ..llm import LLM
from ..retriever.hybrid import HybridRetriever
from .prompts import SYSTEM_PROMPT


class KnowledgeAgent:
    """Orchestrates retrieval + LLM generation."""

    def __init__(self, retriever: HybridRetriever, llm: LLM | None = None):
        self.retriever = retriever
        self.llm = llm or LLM()
        self._conversations: Dict[str, List[dict]] = {}

    def _build_context(self, chunks: List[dict]) -> str:

        parts = []  # 用于存储格式化后的各个文本块
        for i, chunk in enumerate(chunks):  # 遍历所有文本块
        # 从元数据中获取文件名，如果不存在则使用默认值"unknown"
            filename = chunk.get("metadata", {}).get("filename", "unknown")
        # 从元数据中获取块索引，如果不存在则使用当前枚举索引
            cidx = chunk.get("metadata", {}).get("chunk_index", i)
        # 获取相关性分数，如果不存在则默认为0
            score = chunk.get("rrf_score") or chunk.get("score", 0)
        # 将文本块格式化为带有元数据的字符串并添加到parts列表
            parts.append(
                f"--- Chunk {i+1} [source: {filename}, index: {cidx}, relevance: {score:.4f}] ---\n"
                f"{chunk['text']}\n"
            )
    # 将所有格式化后的文本块合并为一个字符串
        return "\n".join(parts)

    def _get_history(self, conv_id: str) -> List[dict]:
        return self._conversations.get(conv_id, [])

    def _add_to_history(self, conv_id: str, role: str, content: str):
        if conv_id not in self._conversations:
            self._conversations[conv_id] = []
        self._conversations[conv_id].append({"role": role, "content": content})
        if len(self._conversations) > 100:
            oldest = min(self._conversations.keys())
            del self._conversations[oldest]

    def query(
        self,question: str,conv_id: str = "default",top_k: int | None = None,doc_ids: Optional[List[str]] = None,) -> dict:
        chunks = self.retriever.retrieve(question, top_k=top_k, doc_ids=doc_ids)

        if not chunks:
            return {
                "answer": "No relevant documents found in the knowledge base. Please upload documents first.",
                "sources": [],
                "conv_id": conv_id,
            }
        context = self._build_context(chunks)
        system_prompt = SYSTEM_PROMPT.format(context=context)
        history = self._get_history(conv_id)
        messages = history + [{"role": "user", "content": question}]

        from ..config import config
        answer = self.llm.generate(
            system=system_prompt,
            messages=messages,
            max_tokens=config.llm_max_tokens,
            temperature=0.3,
        )
        self._add_to_history(conv_id, "user", question)
        self._add_to_history(conv_id, "assistant", answer)
        return {
            "answer": answer,
            "sources": self._extract_sources(chunks),
            "conv_id": conv_id,
            "chunks_used": len(chunks),
        }

    async def query_stream(
        self,
        question: str,
        conv_id: str = "default",
        top_k: int | None = None,
        doc_ids: Optional[List[str]] = None,
    ):
        chunks = self.retriever.retrieve(question, top_k=top_k, doc_ids=doc_ids)

        if not chunks:
            yield json.dumps({"type": "answer", "data": "No relevant documents found in the knowledge base."})
            return

        context = self._build_context(chunks)
        system_prompt = SYSTEM_PROMPT.format(context=context)
        history = self._get_history(conv_id)
        messages = history + [{"role": "user", "content": question}]

        sources = self._extract_sources(chunks)
        yield json.dumps({"type": "sources", "data": sources})

        from ..config import config
        full_answer = ""
        async for token in self.llm.generate_stream(
            system=system_prompt,
            messages=messages,
            max_tokens=config.llm_max_tokens,
            temperature=0.3,
        ):
            full_answer += token
            yield json.dumps({"type": "token", "data": token})

        self._add_to_history(conv_id, "user", question)
        self._add_to_history(conv_id, "assistant", full_answer)
        yield json.dumps({"type": "done", "data": {"conv_id": conv_id, "chunks_used": len(chunks)}})

    def reset_conversation(self, conv_id: str):
        self._conversations.pop(conv_id, None)

    @staticmethod
    def _extract_sources(chunks: List[dict]) -> List[dict]:
        seen = {}
        for c in chunks:
            filename = c.get("metadata", {}).get("filename", "unknown")
            doc_id = c.get("doc_id", "")
            if doc_id not in seen:
                seen[doc_id] = {
                    "doc_id": doc_id,
                    "filename": filename,
                    "source": c.get("metadata", {}).get("source", ""),
                    "chunks": [],
                }
            seen[doc_id]["chunks"].append({
                "chunk_id": c["chunk_id"],
                "chunk_index": c.get("metadata", {}).get("chunk_index", 0),
                "score": c.get("rrf_score") or c.get("score", 0),
                "text_preview": c["text"][:200] + "..." if len(c["text"]) > 200 else c["text"],
            })
        return list(seen.values())
