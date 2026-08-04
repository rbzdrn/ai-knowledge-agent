# AI Knowledge Base Agent

A production-ready AI-powered knowledge base system with **RAG (Retrieval-Augmented Generation)**, hybrid search, and knowledge graph visualization.

## Documentation

| 文档 | 说明 |
|------|------|
| [架构设计](docs/ARCHITECTURE.md) | 系统架构、模块设计、数据流、设计决策 |
| [API 参考](docs/API.md) | 完整 API 文档，含请求/响应示例 |
| [开发指南](docs/DEVELOPMENT.md) | 环境配置、测试、扩展开发、常见问题 |

## Highlights

- **Hybrid Retrieval Engine** — Dense (vector similarity) + Sparse (BM25) with Reciprocal Rank Fusion, giving better recall than pure vector search
- **CJK-Aware Chunking** — Custom recursive text splitter that respects Chinese/Japanese/Korean sentence boundaries alongside English
- **AI Agent with Tool Use** — Claude-powered agent that retrieves relevant context, synthesizes answers with inline citations, and maintains multi-turn conversation state
- **Knowledge Graph** — Entity extraction across documents visualized as an interactive Cytoscape graph showing document-entity relationships
- **Streaming SSE** — Real-time token-by-token streaming responses for a ChatGPT-like experience
- **Zero External Services** — Embedding model runs locally (all-MiniLM-L6-v2, ~80MB); ChromaDB is embedded; only the LLM requires an API key
- **Clean SPA Frontend** — Document upload via drag/drop or URL, chat interface, source citation panel, and knowledge graph tab

## Architecture

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────┐
│  Document    │ ──▶ │  Chunker (CJK-aware) │ ──▶ │  Embedder    │
│  Loader      │     │  Recursive split      │     │  MiniLM-L6   │
│  PDF/DOCX/   │     └─────────────────────┘     └──────┬───────┘
│  MD/Web      │                                        │
└──────────────┘                                ┌───────▼───────┐
                                                │  ChromaDB     │
                                                │  (persistent) │
                                                └───────┬───────┘
┌──────────────┐                                        │
│  User Query  │ ──▶  Hybrid Retriever  ◀───────────────┘
│              │     Dense + BM25 + RRF         ┌───────▼───────┐
└──────────────┘                                │  BM25 Index   │
                                                │  (in-memory)  │
┌──────────────┐                                └───────────────┘
│  Claude      │ ◀── Retrieved Chunks + Query
│  Agent       │
│  (streaming) │ ──▶  Answer + Citations
└──────────────┘
```

## Quick Start

### 1. Install dependencies

```bash
cd ai-knowledge-agent
pip install -r backend/requirements.txt
```

Requires Python 3.10+. First run downloads the embedding model (~80MB) from HuggingFace.

### 2. Choose LLM backend (pick one)

**Option A: Ollama (FREE, recommended)**

Install [Ollama](https://ollama.com), then:

```bash
ollama pull qwen2.5:7b       # Great Chinese support, free
# The app auto-detects Ollama — no config needed
```

**Option B: Anthropic Claude**

```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Option C: DeepSeek (cheap, Chinese-friendly)**

```bash
export DEEPSEEK_API_KEY="sk-..."    # From https://platform.deepseek.com
```

**Option D: OpenAI**

```bash
export OPENAI_API_KEY="sk-..."
```

Auto-detection order: Ollama → Anthropic → DeepSeek → OpenAI. Set `LLM_BACKEND=...` to override.

### 3. Run

```bash
python run.py
```

Open **http://localhost:8000**

### Troubleshooting

| Issue | Fix |
|-------|-----|
| No LLM backend | Install Ollama (free) or set an API key |
| SSL error downloading model | `set HF_HUB_DISABLE_SSL_VERIFY=1` (Win) or `export HF_HUB_DISABLE_SSL_VERIFY=1` (Mac/Linux) |
| ChromaDB import error on Python 3.14 | Upgrade: `pip install --upgrade chromadb` |
| Model download blocked | Download manually from HuggingFace `sentence-transformers/all-MiniLM-L6-v2` to local cache |

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check + chunk/doc counts |
| `POST` | `/api/upload` | Upload a document (`multipart/form-data`) |
| `POST` | `/api/upload-url` | Fetch and index a web page `{"url":"..."}` |
| `GET` | `/api/documents` | List indexed documents |
| `DELETE` | `/api/documents/{id}` | Delete document + chunks |
| `POST` | `/api/chat` | Ask a question `{"question":"..."}` |
| `POST` | `/api/chat/stream` | Streaming chat (SSE) |
| `POST` | `/api/conversation/{id}/reset` | Clear chat history |
| `GET` | `/api/search?q=...&top_k=10` | Retrieve without LLM |
| `GET` | `/api/knowledge-graph` | Cytoscape JSON for graph viz |
| `GET` | `/api/knowledge-graph/stats` | Graph stats |

### Example: Index and query via API

```python
import requests

# Upload documents
requests.post("http://localhost:8000/api/upload",
              files={"file": open("report.pdf", "rb")})

# Ask a question (streaming)
resp = requests.post("http://localhost:8000/api/chat",
                     json={"question": "What are the key findings?"})
print(resp.json()["answer"])
# > Based on the documents, the key findings are:
# > 1. Revenue grew 15% YoY [source: report.pdf]
# > 2. Customer retention improved by 8% [source: report.pdf]

# Simple search without LLM
resp = requests.get("http://localhost:8000/api/search?q=revenue growth")
for r in resp.json()["results"]:
    print(f"[{r['filename']}] {r['text'][:100]}...")
```

## Project Structure

```
ai-knowledge-agent/
├── run.py                       # Startup script
├── README.md
├── backend/
│   ├── main.py                  # FastAPI application (APIs + static serving)
│   ├── config.py                # Centralized configuration
│   ├── embeddings.py            # Local embedding model wrapper
│   ├── requirements.txt
│   ├── document_loader/
│   │   └── loader.py            # PDF, DOCX, Markdown, TXT, Web page parsers
│   ├── chunker/
│   │   └── chunker.py           # CJK-aware recursive text splitter
│   ├── vectordb/
│   │   └── store.py             # ChromaDB CRUD + search wrapper
│   ├── retriever/
│   │   └── hybrid.py            # BM25 implementation + HybridRetriever with RRF
│   ├── agent/
│   │   ├── agent.py             # Claude-powered knowledge agent (streaming + sync)
│   │   └── prompts.py           # System prompts with citation instructions
│   └── kg/
│       └── builder.py           # Entity extraction + NetworkX graph builder
├── frontend/
│   ├── index.html               # Single-page application
│   ├── style.css                # Dark sidebar, 3-column layout, responsive
│   └── app.js                   # Chat, SSE streaming, file upload, Cytoscape graph
└── data/                        # Auto-created at runtime
    ├── uploads/                  # Uploaded files
    └── vectordb/                 # ChromaDB persistence
```

## Key Design Decisions

**Why BM25 + Dense instead of just vector search?** Pure vector search misses exact keyword matches (e.g., product codes, error numbers). BM25 catches those. RRF fusion combines both ranking lists without tuning weights.

**Why ChromaDB over FAISS/Milvus?** ChromaDB is an embedded database — zero config, zero servers. It persists to disk automatically. Perfect for single-machine deployments up to ~1M chunks.

**Why custom chunker instead of LangChain?** LangChain's text splitter doesn't handle CJK sentence boundaries well. Our recursive splitter respects Chinese/Japanese periods and commas alongside English punctuation.

**Why local embeddings?** No API cost for embedding, no rate limits, works offline. The 80MB MiniLM model runs on CPU and produces 384-dim vectors — good enough for most document QA use cases.
#   a i - k n o w l e d g e - a g e n t  
 