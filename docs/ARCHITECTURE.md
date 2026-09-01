# AI Knowledge Base Agent — 架构设计文档

## 1. 项目概述

AI Knowledge Base Agent 是一个基于 RAG（Retrieval-Augmented Generation）的智能知识库系统。用户可以上传多种格式的文档（PDF、DOCX、Markdown、网页等），系统自动完成文档解析、文本切分、向量化存储，并通过混合检索引擎和 Claude AI Agent 提供带原文溯源的智能问答。

### 1.1 核心能力

| 能力 | 描述 |
|------|------|
| 多格式文档摄入 | PDF / DOCX / Markdown / TXT / 网页，自动解析并索引 |
| 混合检索 | Dense（向量相似度）+ Sparse（BM25 关键词）+ RRF 融合排序 |
| AI 智能问答 | Claude 驱动，基于检索到的上下文生成答案，附带来源引用 |
| 多轮对话 | 会话级别的对话历史管理，支持上下文连续问答 |
| 知识图谱 | 自动实体抽取 + 文档-实体关系图可视化 |
| 流式响应 | SSE（Server-Sent Events）实现 token 级别实时输出 |

### 1.2 技术栈

| 层级 | 技术选型 | 选型理由 |
|------|----------|----------|
| Web 框架 | FastAPI + Uvicorn | 原生异步支持，SSE 流式响应，自动生成 API 文档 |
| 向量数据库 | ChromaDB（嵌入式） | 零配置，零运维，SQLite 持久化，单机百万级 chunk 无压力 |
| 嵌入模型 | all-MiniLM-L6-v2 | 本地运行，80MB 体积，384 维向量，CPU 推理毫秒级 |
| LLM | Anthropic Claude (Sonnet/Opus) | 支持超长上下文，原生流式输出，中文能力强 |
| 关键词检索 | 自研 BM25 | 轻量级，CJK 分词感知，与 dense 检索互补 |
| 知识图谱 | NetworkX + Cytoscape.js | 轻量图计算 + 前端交互式可视化 |
| 前端 | 原生 HTML/CSS/JS | 零构建工具，单文件部署，Cytoscape CDN 引入 |

---

## 2. 系统架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Frontend (SPA)                            │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ 文档上传  │  │  聊天界面     │  │  来源面板     │  │  知识图谱   │  │
│  │ (拖拽/URL)│  │  (SSE 流式)  │  │  (溯源引用)   │  │  (Cytoscape)│  │
│  └────┬─────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │
└───────┼───────────────┼─────────────────┼───────────────┼──────────┘
        │               │                 │               │
┌───────┴───────────────┴─────────────────┴───────────────┴──────────┐
│                        FastAPI Server                               │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                       REST API Layer                          │  │
│  │  /upload  /upload-url  /documents  /chat  /chat/stream        │  │
│  │  /search  /knowledge-graph  /conversation/reset  /health      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│  ┌───────────────────────────┴──────────────────────────────────┐  │
│  │                     Core Pipeline                             │  │
│  │                                                               │  │
│  │   ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   │  │
│  │   │ Loader  │──▶│ Chunker  │──▶│ Embedder │──▶│VectorStore│  │  │
│  │   │ PDF/DOCX│   │ CJK-aware│   │ MiniLM   │   │ ChromaDB  │   │  │
│  │   │ MD/Web  │   │ splitter │   │ L6-v2    │   │ persistent│   │  │
│  │   └─────────┘   └──────────┘   └──────────┘   └─────┬─────┘   │  │
│  │                                                      │         │  │
│  │   ┌──────────────────────────────────────────────────┘         │  │
│  │   │                                                            │  │
│  │   ▼                                                            │  │
│  │   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │  │
│  │   │ BM25 Index   │   │HybridRetriever│   │ Knowledge    │      │  │
│  │   │ (in-memory)  │◀──│ Dense+BM25    │   │ Agent        │      │  │
│  │   │              │   │ + RRF fusion  │──▶│ (Claude)     │      │  │
│  │   └──────────────┘   └──────────────┘   └──────┬───────┘      │  │
│  │                                                  │              │  │
│  │   ┌──────────────┐                              │              │  │
│  │   │ Knowledge    │                              ▼              │  │
│  │   │ Graph Builder│                     Streaming Response      │  │
│  │   │ NetworkX     │                              │              │  │
│  │   └──────────────┘                              │              │  │
│  └─────────────────────────────────────────────────┘──────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

#### 文档摄入流（离线）

```
文件上传 → 保存到 data/uploads/
         → DocumentLoader 解析文本
         → TextChunker 切分为 chunk
         → Embedder 批量向量化
         → ChromaDB 持久化存储
         → 重建 BM25 索引（全量）
```

#### 问答流（在线）

```
用户提问 → Embedder 将问题向量化
         → Dense 检索: ChromaDB.top_k(10) 余弦相似度
         → Sparse 检索: BM25.top_k(10) 关键词匹配
         → RRF 融合: 两个排序列表按倒数排名加权合并
         → 取 top_k(8) 个 chunk
         → 组装 System Prompt: 检索上下文 + 引用规则
         → Claude API 流式调用
         → SSE 推送 token + source 信息到前端
         → 历史消息存入会话
```

---

## 3. 模块详细设计

### 3.1 Document Loader (`document_loader/loader.py`)

**职责**: 解析多格式文档，输出统一 `Document` 对象。

```
输入: 文件路径 或 URL
输出: Document(id, filename, content, metadata)

支持格式:
  .pdf  → pypdf.PdfReader 逐页提取文本
  .docx → python-docx 提取段落
  .md   → 直接读取 UTF-8
  .txt  → 直接读取 UTF-8
  URL   → requests + BeautifulSoup，过滤 script/style/nav 标签

文本清洗: 合并多余换行、去除空字符、首尾空白
```

### 3.2 Text Chunker (`chunker/chunker.py`)

**职责**: 将长文本切分为适合检索的短片段，兼顾语义边界。

**切分策略 — CJK 感知递归切分**:

```
分隔符优先级（从粗到细）:
  "\n\n" → "\n" → "。" → ". " → "." → "；" → ";" → " " → 固定宽度

算法:
  1. 用当前分隔符 split 文本
  2. 贪心拼接片段直到接近 chunk_size (默认 500 字符)
  3. 超长片段递归使用下一级分隔符
  4. 相邻 chunk 保留 overlap (默认 50 字符)
  5. 过短片段 (<50字符) 合并到前一个 chunk
```

**设计理由**: LangChain 的 `RecursiveCharacterTextSplitter` 不处理中文句号（。）、分号（；）等边界，导致中文文档切分质量差。自研切分器在保留英文分隔符的同时加入 CJK 标点，显著改善中文检索效果。

### 3.3 Embedder (`embeddings.py`)

**职责**: 文本向量化，本地运行。

```
模型: sentence-transformers/all-MiniLM-L6-v2
维度: 384
归一化: L2 normalize
批处理: 支持 batch 编码
缓存: 首次下载后本地缓存，支持 local_files_only 离线模式

错误处理:
  1. 优先尝试 local_files_only=True（离线/已缓存）
  2. 失败则尝试在线下载
  3. SSL 问题 → 提示设置 HF_HUB_DISABLE_SSL_VERIFY
```

### 3.4 Vector Store (`vectordb/store.py`)

**职责**: ChromaDB 封装，提供文档-向量-元数据的 CRUD。

```
存储结构:
  collection: "knowledge_base"
  每条记录: {id, document, embedding, metadata}
  metadata 包含: doc_id, filename, source, file_type, chunk_index, chunk_count

核心操作:
  add()          - 批量添加 chunk
  search()       - 余弦相似度检索 (1 - distance 转换为 score)
  delete_document() - 按 doc_id 删除全部 chunks
  list_documents()  - 去重后的文档列表
  get_all_chunks()  - 全量导出自建 BM25 索引

索引: HNSW (ChromaDB 内置)，cosine 距离
```

### 3.5 Hybrid Retriever (`retriever/hybrid.py`)

**职责**: 组合稠密检索和稀疏检索，提升召回率。

#### BM25 实现

```
核心公式:
  score(d, q) = Σ IDF(qi) × TF(qi, d) × (k1+1) / (TF(qi, d) + k1 × (1-b + b×|d|/avgdl))

参数:
  k1 = 1.5  控制词频饱和度
  b  = 0.75 控制文档长度归一化

CJK 分词:
  逐字符判断是否字母/数字/CJK字符
  → 空格分割 → 过滤单字符（减少噪音）

优点: 精确匹配产品编号、错误码、专有名词（向量检索容易漏掉）
```

#### RRF（Reciprocal Rank Fusion）融合

```
对每个 chunk c:
  RRF_score(c) = Σ 1/(k + rank_i(c))

其中 k=60（平滑参数），rank_i 是检索器 i 给出的排名

优点:
  - 无需调权重
  - 对排名靠前的结果敏感
  - 自动惩罚在两个检索器中都排名靠后的结果
```

### 3.6 Knowledge Agent (`agent/agent.py`)

**职责**: Claude 驱动的问答代理，管理检索-生成循环和会话状态。

```
处理流程:
  1. 调用 HybridRetriever.retrieve(question)
  2. 格式化检索结果为上下文（含文件名、chunk 索引、相关性分数）
  3. 填充 System Prompt（上下文 + 引用规则）
  4. 获取会话历史
  5. 调用 Claude API（同步或流式）
  6. 提取来源信息
  7. 更新会话历史

会话管理:
  - 内存字典: conv_id → [{role, content}, ...]
  - 超过 100 个会话时删除最旧的
  - 支持手动 reset

System Prompt 核心规则:
  - 仅基于提供的上下文回答
  - 上下文不足时明确告知用户
  - 每条事实引用来源: [source: filename, chunk N]
  - 匹配用户语言
```

### 3.7 Knowledge Graph Builder (`kg/builder.py`)

**职责**: 从文档中抽取实体，构建文档-实体关系图。

```
两种模式:

1. 关键词模式（默认，无需 LLM）:
   - 英文: 正则提取大写开头的短语 (Capitalized Phrases)
   - CJK: 正则提取 2-4 字序列，过滤停用词
   - 统计词频，取 top-8 作为文档关联实体
   - 构建二部图: 文档节点 ←→ 实体节点

2. LLM 模式（可选，更准确）:
   - 每个 chunk 调用 Claude 提取实体
   - 实体类型: person, organization, location, product, technology, concept
   - 返回 JSON 结构化实体列表

图结构:
  - 节点类型: document / entity
  - 边权重: 实体在文档中出现次数
  - 导出: Cytoscape JSON 格式

可视化:
  前端 Cytoscape.js → cose 力导向布局
  文档节点绿色，实体节点紫色
  节点大小由 degree 决定
```

---

## 4. 前端设计

### 4.1 布局

```
┌──────────────┬──────────────────────────┬────────────────┐
│   Sidebar    │      Main Chat           │  Right Panel   │
│   (280px)    │      (flex: 1)           │  (320px)       │
│              │                          │                │
│  ┌Upload──┐  │  ┌──────────────────┐   │  [Sources]     │
│  │+ Upload│  │  │  Welcome Message │   │  [Graph]       │
│  │  URL   │  │  │                  │   │                │
│  └────────┘  │  │  User: 什么是RAG? │   │  ┌source────┐ │
│              │  │  Agent: RAG是...  │   │  │ doc1.pdf  │ │
│  Documents   │  │  [source: doc1]   │   │  │ chunk 3   │ │
│  ┌────────┐  │  │                  │   │  │ 85% match │ │
│  │doc1.pdf│  │  │  User: 如何实现? │   │  └──────────┘ │
│  │doc2.md │  │  │  Agent: ...      │   │                │
│  └────────┘  │  │                  │   │  ┌graph─────┐ │
│              │  │                  │   │  │ ○→○→○    │ │
│  [Clear]    │  │  ┌──────────────┐ │   │  │ ○→○      │ │
│  [Graph]    │  │  │ Type here... │ │   │  │ 12 nodes │ │
│              │  │  │         [➤] │ │   │  └──────────┘ │
└──────────────┴──────────────────────┴────────────────────┘
```

### 4.2 交互流程

```
文件上传:
  点击 Upload 按钮 / 拖拽文件 / 粘贴 URL
  → 显示上传进度
  → 完成时显示 chunk 数量
  → 自动刷新文档列表

聊天:
  输入问题 → Enter / 点击发送
  → 用户气泡出现
  → Agent 气泡 loading 动画
  → SSE 流式 token 逐个追加
  → 完成后显示来源面板
  → 引用文本高亮为可点击样式

图谱:
  点击 "Build Graph" → API 请求
  → Cytoscape 渲染力导向图
  → 可拖拽节点、缩放
  → 显示节点/边统计
```

---

## 5. 关键设计决策

### 5.1 为什么 Dense + Sparse 混合检索？

纯向量检索的缺陷：
- 对专有名词（产品编号、错误码、API名称）不敏感
- "Apple 公司" vs "apple 水果" 在向量空间中距离很近

BM25 互补：
- 精确关键词匹配，对稀有词 IDF 权重高
- 不依赖训练数据分布

RRF 的优势：
- 无需手动调权（不像加权求和需要试出 α 参数）
- 在两个检索器结果集有重叠时效果最好
- 业界验证：比单独 Dense 或 Sparse 的 MAP 提升 5-15%

### 5.2 为什么 ChromaDB 而不是 FAISS/Milvus？

| 方案 | 部署 | 持久化 | API | 适用 |
|------|------|--------|-----|------|
| FAISS | 嵌入式 | 手动 | C++/Python | 研究/离线 |
| Milvus | 需部署服务 | 自动 | gRPC | 企业级/集群 |
| **ChromaDB** | **嵌入式** | **自动(SQLite)** | **Python** | **单机/原型** |

ChromaDB 最适合本项目场景：单机部署、零运维、开箱即用。

### 5.3 为什么自定义 Chunker 而不是 LangChain？

LangChain 的分隔符是硬编码的英文标点（`["\n\n", "\n", " ", ""]`），不处理：
- 中文句号 `。`
- 中文分号 `；`
- 中文感叹号 `！` / 问号 `？`

这导致中文文档切分时经常在句子中间断开，影响检索语义完整性。我们的自定义实现仅 ~100 行，加入了 CJK 标点处理，显著改善中文场景的检索质量。

### 5.4 为什么本地 Embedding 而不是 API？

- **零成本**: 无 API 调用费用
- **零延迟**: 无网络往返
- **离线可用**: 不依赖外部服务
- **隐私**: 文档内容不离开本地
- **够用**: 384 维 MiniLM 在文档 QA 场景与 API 模型差距 <5%

代价仅首次下载 80MB 模型，一次性开销。

---

## 6. 扩展方向

### 6.1 短期改进

- **Cross-encoder Reranker**: 在 RRF 之后用 cross-encoder 精排前 20 个候选（提升精度，增加 ~100ms 延迟）
- **分块策略增强**: 支持按标题/章节切分（Markdown heading-aware splitting）
- **多 Collection 支持**: 按项目/团队隔离知识库
- **图片支持**: PDF 中的图片 OCR / 多模态检索

### 6.2 中期改进

- **增量索引**: 当前每次上传都重建 BM25 全量索引，改为增量更新
- **查询改写**: 使用 LLM 改写用户问题（Query Expansion），提升检索召回
- **用户认证**: JWT 登录 + 多用户知识库隔离
- **批量导入**: 支持 ZIP 上传 / 文件夹导入

### 6.3 长期展望

- **多模态 RAG**: 支持图片、表格、代码的检索
- **Agent 工具扩展**: 允许 Agent 调用外部 API（搜索、计算、数据库查询）
- **自动更新**: 定时爬取 URL，自动更新过期文档
- **协作功能**: 知识库共享、批注、反馈闭环
