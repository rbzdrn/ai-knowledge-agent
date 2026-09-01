"""
Knowledge Graph Builder — extracts entities and relationships from documents.
Uses the LLM for entity extraction and NetworkX for graph construction.
"""

import json
import re
from typing import List, Dict, Tuple
from collections import Counter

import networkx as nx

from ..config import config
from ..vectordb.store import VectorStore


class KnowledgeGraphBuilder:
    """Build a knowledge graph from document chunks using LLM-based entity extraction."""

    def __init__(self, vector_store: VectorStore):
        self.vs = vector_store
        self.graph = nx.Graph()

    def build(self, use_llm: bool = False) -> nx.Graph:
        """Build the knowledge graph from all chunks."""
        self.graph = nx.Graph()
        chunks = self.vs.get_all_chunks()
        if not chunks:
            return self.graph

        if use_llm and config.anthropic_api_key:
            self._build_with_llm(chunks)
        else:
            self._build_with_keywords(chunks)

        return self.graph

    def _build_with_keywords(self, chunks: List[dict]):
        """Fast keyword-based entity extraction without LLM."""
        doc_entities: Dict[str, Counter] = {}

        for chunk in chunks:
            doc_id = chunk["doc_id"]
            filename = chunk.get("metadata", {}).get("filename", doc_id)
            entities = self._extract_keywords(chunk["text"])
            if doc_id not in doc_entities:
                doc_entities[doc_id] = Counter()
            doc_entities[doc_id].update(entities)

        # Add document nodes
        for doc_id, entity_counts in doc_entities.items():
            filename = doc_id
            self.graph.add_node(doc_id, type="document", label=filename[:40], size=20)
            top_entities = entity_counts.most_common(8)
            for entity, count in top_entities:
                if count < 2:
                    continue
                if entity not in self.graph:
                    self.graph.add_node(entity, type="entity", label=entity, size=10)
                self.graph.add_edge(doc_id, entity, weight=count)

    def _build_with_llm(self, chunks: List[dict]):
        """Use LLM to extract entities and relationships."""
        from anthropic import Anthropic
        client = Anthropic(api_key=config.anthropic_api_key)

        for chunk in chunks[:50]:  # Limit to avoid excessive API calls
            try:
                entities = self._llm_extract_entities(client, chunk["text"])
                doc_id = chunk["doc_id"]
                filename = chunk.get("metadata", {}).get("filename", doc_id)
                self.graph.add_node(doc_id, type="document", label=filename[:40], size=20)
                for entity in entities:
                    name = entity.get("name", "").strip()
                    etype = entity.get("type", "concept")
                    if not name or len(name) < 2:
                        continue
                    node_id = f"{name}"
                    if node_id not in self.graph:
                        self.graph.add_node(node_id, type=etype, label=name, size=12)
                    self.graph.add_edge(doc_id, node_id, weight=1)
            except Exception:
                continue

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Simple keyword extraction for CJK + English text."""
        keywords = []
        # English capitalized phrases
        english_phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        keywords.extend([p.lower() for p in english_phrases if len(p) > 5])

        # CJK 2-4 character sequences (potential terms)
        cjk_chars = re.findall(r'[一-鿿]{2,4}', text)
        # Filter common stop patterns
        stop_patterns = {'这是', '一个', '可以', '他们', '我们', '这个', '那个', '什么', '怎么', '为什么', '没有', '已经', '还是', '或者', '因为', '所以', '如果', '虽然', '但是', '而且', '然后', '之后', '之前', '以及', '关于', '对于', '通过', '根据', '按照', '除了', '不仅', '只是', '就是', '还是'}
        keywords.extend([c for c in cjk_chars if c not in stop_patterns])

        return keywords

    @staticmethod
    def _llm_extract_entities(client, text: str) -> List[dict]:
        prompt = f"""Extract up to 5 key entities from this text. For each entity, provide a name and type (person, organization, location, product, technology, concept, event, date).

Return ONLY valid JSON array:
[{{"name": "entity name", "type": "entity type"}}, ...]

Text:
{text[:1500]}
"""
        resp = client.messages.create(
            model="claude-sonne1t-4-6",
            max_tokens=512,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text_resp = resp.content[0].text.strip()
        try:
            text_resp = text_resp[text_resp.index("["):text_resp.rindex("]")+1]
            return json.loads(text_resp)
        except (ValueError, json.JSONDecodeError):
            return []

    def to_cytoscape(self) -> dict:
        """Export graph in Cytoscape-compatible JSON for frontend visualization."""
        elements = []
        for node_id, data in self.graph.nodes(data=True):
            elements.append({
                "data": {
                    "id": node_id,
                    "label": data.get("label", node_id)[:30],
                    "type": data.get("type", "entity"),
                    "size": data.get("size", 10),
                }
            })
        for u, v, data in self.graph.edges(data=True):
            elements.append({
                "data": {
                    "source": u,
                    "target": v,
                    "weight": data.get("weight", 1),
                }
            })
        return {"elements": elements}

    def get_stats(self) -> dict:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "documents": sum(1 for _, d in self.graph.nodes(data=True) if d.get("type") == "document"),
            "entities": sum(1 for _, d in self.graph.nodes(data=True) if d.get("type") != "document"),
        }
