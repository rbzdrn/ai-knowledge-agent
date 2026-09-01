"""
AI Knowledge Base Agent — FastAPI Server
"""

import uuid
import shutil
import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import config
from .embeddings import Embedder
from .document_loader.loader import DocumentLoader
from .chunker.chunker import TextChunker
from .vectordb.store import VectorStore
from .retriever.hybrid import HybridRetriever
from .llm import LLM
from .agent.agent import KnowledgeAgent
from .kg.builder import KnowledgeGraphBuilder

# ── Init ──────────────────────────────────────────────────
embedder = Embedder()
vector_store = VectorStore()
retriever = HybridRetriever(vector_store, embedder)

# LLM auto-detection: Ollama → Anthropic → DeepSeek → OpenAI
try:
    llm = LLM()
    print(f"[Server] LLM backend: {llm.backend_name}")
except RuntimeError as e:
    llm = None
    print(f"[Server] WARNING: No LLM backend available. Chat disabled.")
    print(f"[Server] {e}")

agent = KnowledgeAgent(retriever, llm) if llm else None
chunker = TextChunker()
kg_builder = KnowledgeGraphBuilder(vector_store)

# Build BM25 index from existing data
retriever.build_bm25_index()

app = FastAPI(title="AI Knowledge Base Agent", version="1.0.0")

# ── Models ────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    conv_id: str = "default"
    top_k: int = 8
    doc_ids: Optional[list[str]] = None

class URLUploadRequest(BaseModel):
    url: str

# ── Routes ────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "chunks": vector_store.count(),
        "documents": len(vector_store.list_documents()),
        "llm_backend": llm.backend_name if llm else "none",
        "chat_enabled": agent is not None,
    }

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and index a document."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    # Save uploaded file
    file_path = config.upload_dir / f"{uuid.uuid4().hex[:8]}_{file.filename}"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    return await _process_file(file_path)

@app.post("/api/upload-url")
async def upload_url(req: URLUploadRequest):
    """Fetch and index a web page."""
    try:
        doc = DocumentLoader.load_url(req.url)
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch URL: {e}")

    return _index_document(doc)

@app.get("/api/documents")
def list_documents():
    """List indexed documents."""
    return vector_store.list_documents()

@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    """Delete a document and its chunks."""
    count = vector_store.delete_document(doc_id)
    retriever.build_bm25_index()
    return {"deleted": count, "doc_id": doc_id}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Chat with the knowledge base (non-streaming)."""
    if agent is None:
        raise HTTPException(400, "No LLM backend configured. Install Ollama or set an API key.")

    result = agent.query(
        question=req.question,
        conv_id=req.conv_id,
        top_k=req.top_k,
        doc_ids=req.doc_ids,
    )
    return result

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Chat with the knowledge base (streaming)."""
    if agent is None:
        raise HTTPException(400, "No LLM backend configured. Install Ollama or set an API key.")

    async def stream():
        async for chunk in agent.query_stream(
            question=req.question,
            conv_id=req.conv_id,
            top_k=req.top_k,
            doc_ids=req.doc_ids,
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

@app.post("/api/conversation/{conv_id}/reset")
def reset_conversation(conv_id: str):
    """Reset a conversation."""
    if agent:
        agent.reset_conversation(conv_id)
    return {"status": "reset", "conv_id": conv_id}

@app.get("/api/knowledge-graph")
def get_knowledge_graph(use_llm: bool = False):
    """Get knowledge graph data for visualization."""
    kg_builder.build(use_llm=use_llm)
    return kg_builder.to_cytoscape()

@app.get("/api/knowledge-graph/stats")
def get_kg_stats():
    """Get knowledge graph statistics."""
    kg_builder.build()
    return kg_builder.get_stats()

# ── Internal ──────────────────────────────────────────────
async def _process_file(file_path: Path) -> dict:
    """Process a file: load, chunk, embed, store."""
    try:
        doc = DocumentLoader.load(file_path)
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(400, f"Failed to parse document: {e}")

    return _index_document(doc)


def _index_document(doc) -> dict:
    """Common indexing pipeline for a loaded Document."""
    # Check for duplicates
    existing = vector_store.list_documents()
    for ex in existing:
        if ex.get("source") == doc.metadata.get("source"):
            return {"status": "already_indexed", "doc_id": ex["doc_id"], "filename": doc.filename}

    # Chunk
    chunks = chunker.split(doc.content)
    if not chunks:
        return {"status": "empty", "filename": doc.filename}

    # Embed
    embeddings = embedder.embed_batch(chunks)

    # Add metadata
    metadatas = []
    for i, chunk in enumerate(chunks):
        metadatas.append({
            "doc_id": doc.id,
            "filename": doc.filename,
            "source": doc.metadata.get("source", ""),
            "file_type": doc.metadata.get("file_type", ""),
            "chunk_index": i,
            "chunk_count": len(chunks),
            "char_count": len(chunk),
        })

    # Store
    chunk_ids = vector_store.add(doc.id, chunks, embeddings, metadatas)
    doc.chunk_ids = chunk_ids

    # Rebuild BM25
    retriever.build_bm25_index()

    return {
        "status": "indexed",
        "doc_id": doc.id,
        "filename": doc.filename,
        "chunks": len(chunks),
        "file_type": doc.metadata.get("file_type", ""),
        "char_count": doc.metadata.get("char_count", 0),
    }


@app.get("/api/search")
def simple_search(q: str = Query(...), top_k: int = 10):
    """Simple search without LLM — just retrieve relevant chunks."""
    results = retriever.retrieve(q, top_k=top_k)
    return {
        "query": q,
        "results": [
            {
                "chunk_id": r["chunk_id"],
                "doc_id": r["doc_id"],
                "filename": r.get("metadata", {}).get("filename", ""),
                "text": r["text"],
                "score": r.get("rrf_score") or r.get("score", 0),
                "source": r.get("source", ""),
            }
            for r in results
        ],
    }


# ── Static Files (Frontend) ───────────────────────────────
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/")
async def serve_frontend():
    return FileResponse(frontend_dir / "index.html")


if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
