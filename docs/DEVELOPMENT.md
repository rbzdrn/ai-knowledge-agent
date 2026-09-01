# 开发指南

## 环境要求

| 依赖 | 版本 |
|------|------|
| Python | 3.10 ~ 3.13（3.14 需升级 ChromaDB ≥ 1.5.9） |
| pip | 最新版 |
| 磁盘 | ≥ 2GB（含模型缓存和向量数据库） |
| 内存 | ≥ 4GB |

## 快速开始

### 方式 A：使用 Ollama（免费，推荐）

[Ollama](https://ollama.com) 是一个本地运行大模型的工具，完全免费，无需 API Key。

```bash
# 1. 安装 Ollama
# 从 https://ollama.com 下载安装

# 2. 拉取模型（推荐 qwen2.5:7b，中文效果好）
ollama pull qwen2.5:7b

# 3. 安装项目依赖
cd ai-knowledge-agent
pip install -r backend/requirements.txt

# 4. 启动（自动检测 Ollama）
python run.py
```

### 方式 B：使用 Anthropic Claude

```bash
export ANTHROPIC_API_KEY="sk-ant-..."     # macOS / Linux
$env:ANTHROPIC_API_KEY = "sk-ant-..."     # Windows PowerShell

cd ai-knowledge-agent
pip install -r backend/requirements.txt
python run.py
```

### 方式 C：使用 DeepSeek（便宜，中文友好）

```bash
export DEEPSEEK_API_KEY="sk-..."          # 从 https://platform.deepseek.com 获取
# 或显式指定：export LLM_BACKEND=deepseek

cd ai-knowledge-agent
pip install -r backend/requirements.txt
python run.py
```

### 方式 D：使用 OpenAI

```bash
export OPENAI_API_KEY="sk-..."

cd ai-knowledge-agent
pip install -r backend/requirements.txt
python run.py
```

## LLM 后端配置

系统按以下优先级自动检测可用的 LLM 后端：

| 优先级 | 后端 | 检测条件 | 默认模型 | 费用 |
|--------|------|----------|----------|------|
| 1 | **Ollama** | `localhost:11434` 可达 | `qwen2.5:7b` | 免费 |
| 2 | **Anthropic** | `ANTHROPIC_API_KEY` 已设置 | `claude-sonnet-4-6` | 按量付费 |
| 3 | **DeepSeek** | `DEEPSEEK_API_KEY` 已设置 | `deepseek-chat` | 极低 |
| 4 | **OpenAI** | `OPENAI_API_KEY` 已设置 | `gpt-4o-mini` | 按量付费 |

也可以通过环境变量显式指定：

```bash
export LLM_BACKEND=ollama          # 强制使用 Ollama
export OLLAMA_MODEL=qwen2.5:14b   # 指定模型（默认 qwen2.5:7b）
export OLLAMA_HOST=http://localhost:11434/v1  # Ollama 地址
```

# 5. 启动
python run.py
```

首次运行会自动下载嵌入模型 `all-MiniLM-L6-v2`（~80MB）到 HuggingFace 缓存目录。下载完成后后续启动无需网络。

## 启动方式

### 方式一：使用 run.py（推荐）

```bash
python run.py
```

自动处理 Python path，从项目根目录启动，支持热重载。

### 方式二：使用 uvicorn

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 方式三：指定端口

```bash
python run.py
# 编辑 run.py，修改 port=8000 为其他端口
```

## 项目配置

所有配置集中在 `backend/config.py` 的 `Config` dataclass：

```python
@dataclass
class Config:
    # 嵌入模型
    embedding_model: str = "all-MiniLM-L6-v2"  # 可选: "intfloat/multilingual-e5-base"
    embedding_dim: int = 384
    embedding_device: str = "cpu"               # "cuda" 或 "cpu"

    # 文本切分
    chunk_size: int = 500        # 每个 chunk 的目标字符数
    chunk_overlap: int = 50      # 相邻 chunk 重叠字符数

    # 检索
    dense_top_k: int = 10        # Dense 检索返回数
    sparse_top_k: int = 10       # BM25 检索返回数
    hybrid_top_k: int = 8        # RRF 融合后最终返回数
    use_reranker: bool = False   # 是否启用 Cross-encoder 重排序

    # Agent
    llm_model: str = "claude-sonnet-4-6"  # 或 "claude-opus-4-7"
    llm_max_tokens: int = 2048
    conversation_ttl: int = 3600           # 会话过期时间（秒）

    # 知识图谱
    kg_max_entities_per_chunk: int = 5
```

### 环境变量覆盖

```bash
export ANTHROPIC_API_KEY="sk-ant-..."    # Claude API 密钥（必填）
export HF_HUB_DISABLE_SSL_VERIFY=1       # 跳过 SSL 验证（企业代理环境）
```

## 目录结构

```
ai-knowledge-agent/
├── run.py                       # 启动脚本
├── docs/                        # 文档
│   ├── ARCHITECTURE.md          # 架构设计
│   ├── API.md                   # API 参考
│   └── DEVELOPMENT.md           # 开发指南（本文件）
├── backend/
│   ├── main.py                  # FastAPI 应用 + API 路由
│   ├── config.py                # 全局配置
│   ├── embeddings.py            # 嵌入模型封装
│   ├── requirements.txt
│   ├── document_loader/
│   │   └── loader.py            # 多格式文档解析
│   ├── chunker/
│   │   └── chunker.py           # CJK 感知文本切分
│   ├── vectordb/
│   │   └── store.py             # ChromaDB 封装
│   ├── retriever/
│   │   └── hybrid.py            # BM25 + Dense + RRF 混合检索
│   ├── agent/
│   │   ├── agent.py             # Claude AI Agent
│   │   └── prompts.py           # 系统提示词
│   └── kg/
│       └── builder.py           # 知识图谱构建
├── frontend/
│   ├── index.html               # SPA 入口
│   ├── style.css
│   └── app.js
└── data/                        # 运行时数据（自动创建）
    ├── uploads/                  # 上传的文档
    └── vectordb/                 # ChromaDB 持久化存储
```

## 测试

### 单元测试示例

```python
# test_chunker.py
from backend.chunker.chunker import TextChunker

def test_split():
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    text = "第一段内容。第二段内容。第三段内容。" * 10
    chunks = chunker.split(text)
    assert all(len(c) <= 100 + 20 for c in chunks)  # 允许 overlap 导致的略微超出
    assert len(chunks) > 0

def test_cjk_boundary():
    chunker = TextChunker(chunk_size=200, chunk_overlap=0)
    text = "今天天气很好。我们决定去公园散步。路上遇到了老朋友。"
    chunks = chunker.split(text)
    # 应该在句号处分割
    assert any("。" in c for c in chunks)
```

### API 测试

```bash
# 健康检查
curl http://localhost:8000/api/health

# 创建测试文档
echo "人工智能是计算机科学的一个分支。机器学习是人工智能的核心技术。深度学习使用多层神经网络。" > /tmp/test.txt

# 上传
curl -X POST http://localhost:8000/api/upload -F "file=@/tmp/test.txt"

# 检索
curl "http://localhost:8000/api/search?q=什么是深度学习&top_k=3"

# 问答
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "人工智能包括哪些技术？"}'
```

### 性能基准

| 操作 | 文档规模 | 耗时 |
|------|----------|------|
| PDF 解析 | 50 页 | ~2s |
| 文本切分 | 10万字 | ~0.1s |
| Embedding | 100 chunk | ~0.5s (CPU) |
| Dense 检索 | 10000 chunk | ~10ms |
| BM25 检索 | 10000 chunk | ~50ms |
| RRF 融合 | 20 候选 | ~1ms |
| Claude API | 2000 token 回答 | ~3-8s |

---

## 扩展开发

### 添加新的文档格式

在 `backend/document_loader/loader.py` 的 `DocumentLoader.load()` 中添加分支：

```python
@staticmethod
def load(file_path: str | Path) -> Document:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".epub":
        content = DocumentLoader._load_epub(path)
    elif suffix == ".pdf":
        content = DocumentLoader._load_pdf(path)
    # ... 其他格式

@staticmethod
def _load_epub(path: Path) -> str:
    import ebooklib
    from ebooklib import epub
    book = epub.read_epub(str(path))
    parts = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        parts.append(item.get_body_content().decode())
    return "\n\n".join(parts)
```

### 添加新的 Embedding 模型

修改 `config.py` 中的 `embedding_model`：

```python
# 多语言模型（中英文效果更好，但更大更慢）
embedding_model: str = "intfloat/multilingual-e5-base"
embedding_dim: int = 768

# OpenAI Embedding API（需要 API Key）
embedding_model: str = "text-embedding-3-small"
# 需同步修改 embeddings.py 支持 API 调用
```

### 添加 Cross-encoder Reranker

在 `backend/retriever/` 下创建 `reranker.py`：

```python
from sentence_transformers import CrossEncoder

class Reranker:
    def __init__(self, model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
        pairs = [(query, c["text"]) for c in chunks]
        scores = self.model.predict(pairs)
        for i, score in enumerate(scores):
            chunks[i]["rerank_score"] = float(score)
        chunks.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        return chunks[:top_k]
```

### 添加用户认证

```python
# 在 main.py 中添加中间件
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

def verify_token(credentials = Depends(security)):
    token = credentials.credentials
    # 验证 JWT token
    if not valid_token(token):
        raise HTTPException(401, "Invalid token")
    return decode_token(token)

@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    user = Depends(verify_token)
):
    # user 包含用户信息，用于隔离知识库
    ...
```

---

## 常见问题

### Q: 嵌入模型下载失败？

```bash
# 方案 1：使用镜像
export HF_ENDPOINT=https://hf-mirror.com

# 方案 2：跳过 SSL 验证
export HF_HUB_DISABLE_SSL_VERIFY=1

# 方案 3：手动下载
# 从 https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
# 下载所有文件到 ~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2/
```

### Q: ChromaDB 导入错误？

```bash
pip install --upgrade chromadb
# 确保版本 ≥ 1.5.0
```

### Q: 如何清理所有数据？

```bash
rm -rf data/vectordb/ data/uploads/
# 重启服务后自动重建
```

### Q: 如何查看 ChromaDB 中的原始数据？

```python
from backend.vectordb.store import VectorStore
vs = VectorStore()
chunks = vs.get_all_chunks()
print(f"Total chunks: {len(chunks)}")
for c in chunks[:5]:
    print(f"  [{c['metadata']['filename']}] {c['text'][:100]}")
```

### Q: 前端如何适配移动端？

CSS 已包含响应式断点：
- `≤ 900px`: 隐藏右侧面板（来源/图谱）
- `≤ 600px`: 隐藏左侧边栏（文档列表），聊天区占满全屏

---

## 依赖清单

| 包名 | 用途 | 大小 |
|------|------|------|
| `fastapi` | Web 框架 | ~100KB |
| `uvicorn` | ASGI 服务器 | ~200KB |
| `anthropic` | Claude API SDK | ~500KB |
| `sentence-transformers` | 嵌入模型框架 | ~200KB |
| `chromadb` | 向量数据库 | ~50MB |
| `pypdf` | PDF 解析 | ~2MB |
| `python-docx` | DOCX 解析 | ~200KB |
| `beautifulsoup4` | HTML 解析 | ~400KB |
| `numpy` | 数值计算 | ~20MB |
| `networkx` | 图计算 | ~2MB |

模型下载（首次运行）：
- `all-MiniLM-L6-v2`: ~80MB
- 如启用 reranker `ms-marco-MiniLM-L-6-v2`: ~80MB
