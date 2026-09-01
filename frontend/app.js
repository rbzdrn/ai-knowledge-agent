/**
 * AI Knowledge Base Agent — Frontend Application
 */

const API = '/api';
let convId = 'default';
let cyInstance = null;

// ═══════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  loadDocuments();
  checkHealth();
  setupEventListeners();
});

function checkHealth() {
  fetch(`${API}/health`)
    .then(r => r.json())
    .then(data => {
      document.getElementById('chunkCount').textContent =
        `${data.chunks} chunks · ${data.documents} docs`;
      if (!data.chat_enabled) {
        setStatus('Chat disabled — no LLM backend. Install Ollama or set an API key.', 'error');
      } else {
        setStatus(`Ready · LLM: ${data.llm_backend}`);
      }
    })
    .catch(() => setStatus('Server not reachable', 'error'));
}

// ═══════════════════════════════════════════
//  EVENT LISTENERS
// ═══════════════════════════════════════════

function setupEventListeners() {
  // File upload
  document.getElementById('fileInput').addEventListener('change', handleFileUpload);
  document.getElementById('uploadBtn').addEventListener('click', () => {
    document.getElementById('fileInput').click();
  });

  // URL upload
  document.getElementById('urlBtn').addEventListener('click', handleUrlUpload);
  document.getElementById('urlInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleUrlUpload();
  });

  // Chat
  document.getElementById('sendBtn').addEventListener('click', sendMessage);
  document.getElementById('chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Auto-resize textarea
  document.getElementById('chatInput').addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
  });

  // Clear chat
  document.getElementById('clearChatBtn').addEventListener('click', () => {
    fetch(`${API}/conversation/${convId}/reset`, { method: 'POST' })
      .then(() => {
        document.getElementById('chatMessages').innerHTML = '';
        addWelcomeMessage();
        setStatus('Conversation cleared');
      });
  });

  // Build graph
  document.getElementById('buildGraphBtn').addEventListener('click', loadKnowledgeGraph);

  // Panel tabs
  document.querySelectorAll('.panel-tabs .tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.panel-tabs .tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.dataset.tab;
      document.getElementById('sourcesPanel').style.display = target === 'sources' ? '' : 'none';
      document.getElementById('graphPanel').style.display = target === 'graph' ? '' : 'none';
      if (target === 'graph' && !cyInstance) loadKnowledgeGraph();
    });
  });
}

// ═══════════════════════════════════════════
//  FILE / URL UPLOAD
// ═══════════════════════════════════════════

async function handleFileUpload(e) {
  const files = e.target.files;
  if (!files.length) return;

  const statusEl = document.getElementById('uploadStatus');
  for (const file of files) {
    statusEl.textContent = `Uploading ${file.name}...`;
    statusEl.className = 'upload-status';

    const formData = new FormData();
    formData.append('file', file);

    try {
      const resp = await fetch(`${API}/upload`, { method: 'POST', body: formData });
      const data = await resp.json();
      if (resp.ok) {
        statusEl.textContent = `✓ ${data.filename} (${data.chunks} chunks)`;
        statusEl.className = 'upload-status success';
        loadDocuments();
      } else {
        statusEl.textContent = `✗ ${data.detail || 'Upload failed'}`;
        statusEl.className = 'upload-status error';
      }
    } catch (err) {
      statusEl.textContent = `✗ ${err.message}`;
      statusEl.className = 'upload-status error';
    }
  }
  e.target.value = '';
}

async function handleUrlUpload() {
  const input = document.getElementById('urlInput');
  const url = input.value.trim();
  if (!url) return;

  const statusEl = document.getElementById('uploadStatus');
  statusEl.textContent = 'Fetching URL...';
  statusEl.className = 'upload-status';

  try {
    const resp = await fetch(`${API}/upload-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    const data = await resp.json();
    if (resp.ok) {
      statusEl.textContent = `✓ ${data.filename} (${data.chunks} chunks)`;
      statusEl.className = 'upload-status success';
      loadDocuments();
    } else {
      statusEl.textContent = `✗ ${data.detail || 'Failed'}`;
      statusEl.className = 'upload-status error';
    }
  } catch (err) {
    statusEl.textContent = `✗ ${err.message}`;
    statusEl.className = 'upload-status error';
  }
  input.value = '';
}

// ═══════════════════════════════════════════
//  DOCUMENT LIST
// ═══════════════════════════════════════════

async function loadDocuments() {
  try {
    const resp = await fetch(`${API}/documents`);
    const docs = await resp.json();
    const list = document.getElementById('docList');
    document.getElementById('docCount').textContent = docs.length;

    list.innerHTML = docs.map(doc => `
      <li class="doc-item" title="${doc.filename}">
        <span class="doc-icon">${fileIcon(doc.file_type)}</span>
        <span class="doc-name">${doc.filename}</span>
        <span class="doc-chunks">${doc.chunk_count}c</span>
        <span class="doc-delete" data-id="${doc.doc_id}" title="Delete">×</span>
      </li>
    `).join('');

    list.querySelectorAll('.doc-delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const docId = btn.dataset.id;
        await fetch(`${API}/documents/${docId}`, { method: 'DELETE' });
        loadDocuments();
      });
    });
  } catch (err) {
    console.error('Failed to load documents:', err);
  }
}

function fileIcon(type) {
  const icons = { '.pdf': '📄', '.docx': '📝', '.doc': '📝', '.md': '📋', '.txt': '📃', 'web': '🌐' };
  return icons[type] || '📎';
}

// ═══════════════════════════════════════════
//  CHAT
// ═══════════════════════════════════════════

async function sendMessage() {
  const input = document.getElementById('chatInput');
  const question = input.value.trim();
  if (!question) return;

  input.value = '';
  input.style.height = 'auto';

  // Clear welcome
  const welcome = document.querySelector('.welcome');
  if (welcome) welcome.remove();

  // Add user message
  addMessage('user', question);
  setStatus('Searching knowledge base...');

  // Add assistant placeholder
  const assistantMsg = addMessage('assistant', '', true);

  // Stream response
  try {
    const resp = await fetch(`${API}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, conv_id: convId }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      assistantMsg.querySelector('.content').textContent =
        `Error: ${err.detail || 'Request failed'}`;
      assistantMsg.querySelector('.content').classList.remove('loading-dots');
      setStatus('Error', 'error');
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let sourceData = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // incomplete line

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(line.slice(6));
          handleStreamEvent(data, assistantMsg);
          if (data.type === 'sources') sourceData = data.data;
        } catch (e) { /* skip malformed */ }
      }
    }

    assistantMsg.querySelector('.content').classList.remove('loading-dots');
    if (sourceData) showSources(sourceData);
    setStatus('Ready');
  } catch (err) {
    assistantMsg.querySelector('.content').textContent = `Network error: ${err.message}`;
    assistantMsg.querySelector('.content').classList.remove('loading-dots');
    setStatus('Network error', 'error');
  }
}

function handleStreamEvent(data, msgEl) {
  const contentEl = msgEl.querySelector('.content');

  if (data.type === 'token') {
    if (contentEl.classList.contains('loading-dots')) {
      contentEl.textContent = '';
      contentEl.classList.remove('loading-dots');
    }
    contentEl.textContent += data.data;
    scrollToBottom();
  } else if (data.type === 'done') {
    // Streaming complete
    scrollToBottom();
  }
}

function addMessage(role, content, isLoading = false) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = `message ${role}`;

  let contentHtml = '';
  if (isLoading) {
    contentHtml = '<span class="loading-dots">Searching</span>';
  } else {
    contentHtml = formatContent(content);
  }

  div.innerHTML = `
    <div class="role">${role === 'user' ? 'You' : 'Agent'}</div>
    <div class="content${isLoading ? ' loading-dots' : ''}">${contentHtml}</div>
  `;
  container.appendChild(div);
  scrollToBottom();
  return div;
}

function addWelcomeMessage() {
  const container = document.getElementById('chatMessages');
  container.innerHTML = `
    <div class="welcome">
      <h2>AI Knowledge Base Agent</h2>
      <p>Upload documents and ask questions. I'll find answers with source citations.</p>
      <p class="hint">支持中文提问 · PDF / DOCX / Markdown / Web</p>
    </div>
  `;
}

function formatContent(text) {
  if (!text) return '';
  // Simple markdown-like formatting
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g,
    '<pre><code>$2</code></pre>');

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Bold
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Italic
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

  // Source citations: [source: filename, chunk N]
  html = html.replace(/\[source:\s*([^\]]+)\]/g,
    '<span class="citation">[$1]</span>');

  // Line breaks
  html = html.replace(/\n\n/g, '</p><p>');
  html = html.replace(/\n/g, '<br>');

  // Wrap in paragraph
  if (!html.startsWith('<')) html = '<p>' + html + '</p>';

  return html;
}

function scrollToBottom() {
  const container = document.getElementById('chatMessages');
  container.scrollTop = container.scrollHeight;
}

// ═══════════════════════════════════════════
//  SOURCES PANEL
// ═══════════════════════════════════════════

function showSources(sources) {
  const panel = document.getElementById('sourcesPanel');
  if (!sources || !sources.length) {
    panel.innerHTML = '<p class="dim">No sources found.</p>';
    return;
  }

  panel.innerHTML = sources.map(src => `
    <div class="source-item">
      <span class="source-score">
        ${src.chunks.map(c => (c.score * 100).toFixed(0)).join('/ ')}%
      </span>
      <div class="source-filename">${src.filename}</div>
      <div class="source-meta">${src.chunks.length} chunks matched</div>
      ${src.chunks.slice(0, 3).map(c => `
        <div class="source-preview">${escapeHtml(c.text_preview)}</div>
      `).join('')}
    </div>
  `).join('');

  // Switch to sources tab
  document.querySelector('.tab[data-tab="sources"]').click();
}

// ═══════════════════════════════════════════
//  KNOWLEDGE GRAPH
// ═══════════════════════════════════════════

async function loadKnowledgeGraph() {
  const panel = document.getElementById('graphPanel');
  panel.querySelector('#cyContainer').innerHTML =
    '<p style="text-align:center;padding-top:180px;color:var(--text-dim)">Building graph...</p>';

  try {
    const resp = await fetch(`${API}/knowledge-graph`);
    const data = await resp.json();
    renderGraph(data);

    const statsResp = await fetch(`${API}/knowledge-graph/stats`);
    const stats = await statsResp.json();
    document.getElementById('graphStats').textContent =
      `${stats.nodes} nodes · ${stats.edges} edges · ${stats.documents} docs · ${stats.entities} entities`;
  } catch (err) {
    panel.querySelector('#cyContainer').innerHTML =
      '<p style="text-align:center;padding-top:180px;color:var(--danger)">Failed to load graph</p>';
  }
}

function renderGraph(data) {
  const container = document.getElementById('cyContainer');
  container.innerHTML = '';

  if (cyInstance) cyInstance.destroy();

  cyInstance = cytoscape({
    container,
    elements: data.elements,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': '#4f46e5',
          'label': 'data(label)',
          'font-size': '9px',
          'color': '#1a1d23',
          'text-valign': 'center',
          'text-halign': 'center',
          'width': 'mapData(size, 5, 30, 8, 30)',
          'height': 'mapData(size, 5, 30, 8, 30)',
        },
      },
      {
        selector: 'node[type="document"]',
        style: {
          'background-color': '#10b981',
          'font-weight': 'bold',
          'font-size': '10px',
        },
      },
      {
        selector: 'edge',
        style: {
          'width': 'mapData(weight, 1, 10, 0.5, 3)',
          'line-color': '#d1d5db',
          'opacity': 0.6,
        },
      },
    ],
    layout: {
      name: 'cose',
      animate: false,
      nodeRepulsion: 4000,
      idealEdgeLength: 80,
    },
    minZoom: 0.3,
    maxZoom: 3,
  });

  cyInstance.on('tap', 'node', function(evt) {
    const node = evt.target;
    console.log('Node:', node.data());
  });
}

// ═══════════════════════════════════════════
//  UTILS
// ═══════════════════════════════════════════

function setStatus(text, type = '') {
  const el = document.getElementById('statusText');
  el.textContent = text;
  el.style.color = type === 'error' ? 'var(--danger)' : '';
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function generateConvId() {
  convId = 'conv_' + Math.random().toString(36).slice(2, 8);
  return convId;
}
