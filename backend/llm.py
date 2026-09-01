"""
Unified LLM backend — supports Anthropic, OpenAI, DeepSeek, and Ollama (free local).

Auto-detection priority:
  1. OLLAMA_HOST set or Ollama reachable → Ollama (free, local)
  2. ANTHROPIC_API_KEY set → Anthropic Claude
  3. DEEPSEEK_API_KEY set → DeepSeek
  4. OPENAI_API_KEY set → OpenAI
  5. Fallback: try Ollama at localhost:11434
"""

import os
from typing import List, Dict, Optional, AsyncIterator


class LLMBackend:
    """Abstract base for LLM backends."""

    def generate(
        self,
        system: str,
        messages: List[dict],
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> str:
        raise NotImplementedError

    async def generate_stream(
        self,
        system: str,
        messages: List[dict],
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ):
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError


class AnthropicBackend(LLMBackend):
    """Claude via Anthropic API."""

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    @property
    def name(self) -> str:
        return f"Anthropic/{self.model}"

    def generate(self, system, messages, max_tokens=2048, temperature=0.3):
        from anthropic import Anthropic
        client = Anthropic(api_key=self.api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            temperature=temperature,
        )
        return resp.content[0].text

    async def generate_stream(self, system, messages, max_tokens=2048, temperature=0.3):
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=self.api_key)
        async with client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            temperature=temperature,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    yield event.delta.text
                elif event.type == "message_stop":
                    break


class OpenAICompatibleBackend(LLMBackend):
    """OpenAI / DeepSeek / Ollama — all use OpenAI-compatible chat completions API."""

    def __init__(self, model: str, api_key: str, base_url: str, label: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self._label = label

    @property
    def name(self) -> str:
        return f"{self._label}/{self.model}"

    def _build_payload(self, system, messages, max_tokens, temperature):
        # Merge system prompt into messages for OpenAI format
        full_messages = [{"role": "system", "content": system}] + list(messages)
        return {
            "model": self.model,
            "messages": full_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    def generate(self, system, messages, max_tokens=2048, temperature=0.3):
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        payload = self._build_payload(system, messages, max_tokens, temperature)
        payload["stream"] = False
        resp = client.chat.completions.create(**payload)
        return resp.choices[0].message.content or ""

    async def generate_stream(self, system, messages, max_tokens=2048, temperature=0.3):
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        payload = self._build_payload(system, messages, max_tokens, temperature)
        payload["stream"] = True
        stream = await client.chat.completions.create(**payload)
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content


class LLM:
    """Unified LLM interface with auto-detection."""

    def __init__(
        self,
        backend: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self._backend = self._resolve(backend, model, api_key, base_url)

    def _resolve(self, backend, model, api_key, base_url):
        """Auto-detect the best available backend."""
        bt = (backend or os.environ.get("LLM_BACKEND", "")).lower()

        # ── Explicit backend selection ──
        if bt == "ollama":
            ollama_model = model or self._detect_ollama_model()
            return OpenAICompatibleBackend(
                model=ollama_model,
                api_key="ollama",
                base_url=base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434/v1"),
                label="Ollama",
            )
        if bt == "deepseek":
            key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
            if not key:
                raise ValueError("DEEPSEEK_API_KEY required when backend=deepseek")
            return OpenAICompatibleBackend(
                model=model or "deepseek-chat",
                api_key=key,
                base_url="https://api.deepseek.com/v1",
                label="DeepSeek",
            )
        if bt == "openai":
            key = api_key or os.environ.get("OPENAI_API_KEY", "")
            if not key:
                raise ValueError("OPENAI_API_KEY required when backend=openai")
            return OpenAICompatibleBackend(
                model=model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                api_key=key,
                base_url=base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                label="OpenAI",
            )
        if bt == "anthropic" or bt == "claude":
            key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
            if not key:
                raise ValueError("ANTHROPIC_API_KEY required when backend=anthropic")
            return AnthropicBackend(
                model=model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
                api_key=key,
            )

        # ── Auto-detect: try Ollama first (free, works offline) ──
        if self._ollama_available():
            m = model or self._detect_ollama_model()
            print(f"[LLM] Auto-detected Ollama → {m}")
            return OpenAICompatibleBackend(
                model=m, api_key="ollama",
                base_url=base_url or os.environ.get("OLLAMA_HOST", "http://localhost:11434/v1"),
                label="Ollama",
            )

        # ── Anthropic ──
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if key:
            m = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
            print(f"[LLM] Using Anthropic → {m}")
            return AnthropicBackend(model=m, api_key=key)

        # ── DeepSeek ──
        key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if key:
            print(f"[LLM] Using DeepSeek → deepseek-chat")
            return OpenAICompatibleBackend(
                model=model or "deepseek-chat", api_key=key,
                base_url="https://api.deepseek.com/v1", label="DeepSeek",
            )

        # ── OpenAI ──
        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if key:
            m = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            print(f"[LLM] Using OpenAI → {m}")
            return OpenAICompatibleBackend(
                model=m, api_key=key,
                base_url=base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                label="OpenAI",
            )

        raise RuntimeError(
            "No LLM backend available.\n\n"
            "Options:\n"
            "  1. Install Ollama (FREE): https://ollama.com\n"
            "     Then: ollama pull qwen2.5:7b\n"
            "  2. Set ANTHROPIC_API_KEY env var\n"
            "  3. Set DEEPSEEK_API_KEY env var (cheap, Chinese-friendly)\n"
            "  4. Set OPENAI_API_KEY env var\n"
            "  5. Set LLM_BACKEND=ollama|anthropic|deepseek|openai\n"
        )

    @staticmethod
    def _ollama_available() -> bool:
        """Check if Ollama is running locally."""
        try:
            import urllib.request, json as _json
            url = (os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/v1") + "/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = _json.loads(resp.read())
            return len(data.get("models", [])) > 0
        except Exception:
            return False

    @staticmethod
    def _detect_ollama_model() -> str:
        """Auto-detect best available Ollama model."""
        try:
            import urllib.request, json as _json
            url = (os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/v1") + "/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = _json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            # Filter out embedding-only models
            chat_models = [m for m in models if "embed" not in m.lower() and "bge" not in m.lower()]
            if not chat_models:
                chat_models = models
            # Prefer qwen > llama > deepseek > first available
            for prefix in ("qwen", "llama", "deepseek", "mistral", "gemma", "phi"):
                for m in chat_models:
                    if m.startswith(prefix):
                        return m.replace(":latest", "")
            return chat_models[0] if chat_models else "qwen2.5"
        except Exception:
            return "qwen2.5"

    # ── Delegate to backend ──

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def generate(self, system, messages, max_tokens=2048, temperature=0.3) -> str:
        return self._backend.generate(system, messages, max_tokens, temperature)

    async def generate_stream(self, system, messages, max_tokens=2048, temperature=0.3):
        async for token in self._backend.generate_stream(system, messages, max_tokens, temperature):
            yield token
