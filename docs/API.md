# API 参考文档

Base URL: `http://localhost:8000`

---

## 健康检查

### `GET /api/health`

返回服务状态和存储统计。

**Response** `200 OK`
```json
{
  "status": "ok",
  "chunks": 156,
  "documents": 5,
  "llm_backend": "Ollama/qwen2.5:7b",
  "chat_enabled": true
}
```

| 字段 | 说明 |
|------|------|
| `status` | 服务状态 |
| `chunks` | 已索引 chunk 总数 |
| `documents` | 文档数量 |
| `llm_backend` | 当前 LLM 后端（`Ollama/...`、`Anthropic/...`、`none` 等） |
| `chat_enabled` | 聊天功能是否可用 |

---

## 文档管理

### `POST /api/upload`

上传并索引文档。支持 PDF、DOCX、MD、TXT、HTML。

**Request** `multipart/form-data`
```
file: <binary>
```

**Response** `200 OK`
```json
{
  "status": "indexed",
  "doc_id": "a1b2c3d4",
  "filename": "年度报告.pdf",
  "chunks": 24,
  "file_type": ".pdf",
  "char_count": 12340
}
```

**Response** `200 OK`（重复文档）
```json
{
  "status": "already_indexed",
  "doc_id": "a1b2c3d4",
  "filename": "年度报告.pdf"
}
```

**Error** `400`
```json
{
  "detail": "Failed to parse document: Unsupported file format: .exe"
}
```

---

### `POST /api/upload-url`

抓取网页内容并索引。自动提取正文，过滤脚本/样式/导航。

**Request** `application/json`
```json
{
  "url": "https://example.com/article"
}
```

**Response** `200 OK`
```json
{
  "status": "indexed",
  "doc_id": "e5f6g7h8",
  "filename": "Article Title",
  "chunks": 8,
  "file_type": "web",
  "char_count": 4500
}
```

**Error** `400`
```json
{
  "detail": "Failed to fetch URL: Connection timeout"
}
```

---

### `GET /api/documents`

列出所有已索引文档。

**Response** `200 OK`
```json
[
  {
    "doc_id": "a1b2c3d4",
    "filename": "年度报告.pdf",
    "source": "/data/uploads/xxx_年度报告.pdf",
    "file_type": ".pdf",
    "chunk_count": 24
  },
  {
    "doc_id": "e5f6g7h8",
    "filename": "Article Title",
    "source": "https://example.com/article",
    "file_type": "web",
    "chunk_count": 8
  }
]
```

---

### `DELETE /api/documents/{doc_id}`

删除指定文档及其所有 chunk。

**Response** `200 OK`
```json
{
  "deleted": 24,
  "doc_id": "a1b2c3d4"
}
```

---

## 智能问答

### `POST /api/chat`

同步问答（等待完整回复后返回）。

**Request** `application/json`
```json
{
  "question": "2024年第三季度营收是多少？",
  "conv_id": "default",
  "top_k": 8,
  "doc_ids": ["a1b2c3d4"]
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `question` | string | 是 | — | 用户问题 |
| `conv_id` | string | 否 | `"default"` | 会话 ID，用于多轮对话 |
| `top_k` | int | 否 | `8` | 返回的检索结果数量 |
| `doc_ids` | string[] | 否 | `null` | 限定检索范围到指定文档 |

**Response** `200 OK`
```json
{
  "answer": "根据文档，2024年Q3营收为5.2亿元，同比增长15% [source: 年度报告.pdf, chunk 3]。其中产品收入占比68%，服务收入占比32% [source: 年度报告.pdf, chunk 5]。",
  "sources": [
    {
      "doc_id": "a1b2c3d4",
      "filename": "年度报告.pdf",
      "source": "/data/uploads/xxx_年度报告.pdf",
      "chunks": [
        {
          "chunk_id": "a1b2c3d4_chunk_3",
          "chunk_index": 3,
          "score": 0.045123,
          "text_preview": "2024年第三季度财务摘要：本季度实现营收5.2亿元..."
        },
        {
          "chunk_id": "a1b2c3d4_chunk_5",
          "chunk_index": 5,
          "score": 0.032567,
          "text_preview": "收入结构方面，产品收入占比68%..."
        }
      ]
    }
  ],
  "conv_id": "default",
  "chunks_used": 8
}
```

---

### `POST /api/chat/stream`

流式问答（SSE），token 级别实时输出。

**Request** 同 `/api/chat`

**Response** `text/event-stream`

```
data: {"type":"sources","data":[{...}]}

data: {"type":"token","data":"根"}

data: {"type":"token","data":"据"}

data: {"type":"token","data":"文档"}

data: {"type":"token","data":"，"}

...

data: {"type":"done","data":{"conv_id":"default","chunks_used":8}}
```

**SSE 事件类型**

| type | 说明 | data 内容 |
|------|------|-----------|
| `sources` | 最先发送，包含所有检索来源 | 来源数组（同 `/chat` 的 sources） |
| `token` | 每个文本片段 | 单次生成的文本 token |
| `done` | 流结束 | `{conv_id, chunks_used}` |

**前端消费示例**
```javascript
const resp = await fetch('/api/chat/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ question: '...' })
});

const reader = resp.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  // 解析 SSE: "data: {...}\n\n"
  for (const line of decoder.decode(value).split('\n')) {
    if (line.startsWith('data: ')) {
      const event = JSON.parse(line.slice(6));
      if (event.type === 'token') appendToChat(event.data);
      if (event.type === 'sources') showSources(event.data);
      if (event.type === 'done') finalize();
    }
  }
}
```

---

### `POST /api/conversation/{conv_id}/reset`

清除指定会话的对话历史。

**Response** `200 OK`
```json
{
  "status": "reset",
  "conv_id": "default"
}
```

---

## 检索（无 LLM）

### `GET /api/search`

纯检索接口，不调用 LLM。用于调试或仅需要找到相关 chunk 的场景。

**Query Parameters**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `q` | string | 必填 | 搜索查询 |
| `top_k` | int | `10` | 返回结果数 |

**Response** `200 OK`
```json
{
  "query": "营收增长",
  "results": [
    {
      "chunk_id": "a1b2c3d4_chunk_3",
      "doc_id": "a1b2c3d4",
      "filename": "年度报告.pdf",
      "text": "2024年Q3营收实现5.2亿元，同比增长15%...",
      "score": 0.045123,
      "source": "both"
    },
    {
      "chunk_id": "e5f6g7h8_chunk_2",
      "doc_id": "e5f6g7h8",
      "filename": "行业分析.md",
      "text": "行业整体营收规模突破200亿...",
      "score": 0.031200,
      "source": "dense"
    }
  ]
}
```

`source` 字段含义：
- `"dense"` — 仅被向量检索命中
- `"sparse"` — 仅被 BM25 命中
- `"both"` — 两个检索器都命中（最可靠）

---

## 知识图谱

### `GET /api/knowledge-graph`

获取 Cytoscape.js 格式的图数据。

**Query Parameters**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_llm` | bool | `false` | 是否用 LLM 抽取实体（更准确但更慢） |

**Response** `200 OK`
```json
{
  "elements": [
    {
      "data": {
        "id": "a1b2c3d4",
        "label": "年度报告.pdf",
        "type": "document",
        "size": 20
      }
    },
    {
      "data": {
        "id": "营收增长",
        "label": "营收增长",
        "type": "entity",
        "size": 10
      }
    },
    {
      "data": {
        "source": "a1b2c3d4",
        "target": "营收增长",
        "weight": 4
      }
    }
  ]
}
```

### `GET /api/knowledge-graph/stats`

获取图谱统计信息。

**Response** `200 OK`
```json
{
  "nodes": 45,
  "edges": 72,
  "documents": 5,
  "entities": 40
}
```

---

## 错误码

| HTTP 状态码 | 原因 | 常见触发场景 |
|-------------|------|-------------|
| `400` | 请求参数错误 | ANTHROPIC_API_KEY 未设置时调用 `/chat`；不支持的文档格式 |
| `404` | 资源不存在 | 删除不存在的文档 |
| `500` | 服务器内部错误 | ChromaDB 损坏；依赖缺失 |
