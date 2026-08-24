"""Cliente HTTP para endpoints OpenAI-compativeis. Somente stdlib."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Iterator

USER_AGENT = "llm-council/0.1"
RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def as_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total,
        }


@dataclass
class Reply:
    """Resultado de uma chamada. Falha nunca e silenciosa: ok=False + error preenchido."""

    ok: bool
    content: str = ""
    reasoning: str = ""
    error: str = ""
    usage: Usage = field(default_factory=Usage)
    latency_s: float = 0.0
    attempts: int = 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "content": self.content,
            "reasoning": self.reasoning,
            "error": self.error,
            "usage": self.usage.as_dict(),
            "latency_s": round(self.latency_s, 2),
            "attempts": self.attempts,
        }


class ProviderError(Exception):
    def __init__(self, status: int | None, body: str):
        self.status = status
        self.body = body
        super().__init__(f"HTTP {status}: {body[:400]}")


class Endpoint:
    """Um provedor OpenAI-compativel (openai, deepseek, z.ai, ...)."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str | None,
        headers: dict[str, str] | None = None,
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.extra_headers = headers or {}

    # ------------------------------------------------------------------ HTTP

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        h.update(self.extra_headers)
        return h

    def _request(self, path: str, payload: dict | None, timeout: float, method: str = "POST"):
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            raise ProviderError(e.code, body) from None
        except urllib.error.URLError as e:
            raise ProviderError(None, f"{type(e.reason).__name__}: {e.reason}") from None
        except TimeoutError:
            raise ProviderError(None, f"timeout apos {timeout}s") from None

    # ------------------------------------------------------------------ API

    def list_models(self, timeout: float = 30.0) -> list[str]:
        resp = self._request("/models", None, timeout, method="GET")
        data = json.loads(resp.read().decode())
        items = data.get("data", data if isinstance(data, list) else [])
        out = []
        for it in items:
            if isinstance(it, dict) and it.get("id"):
                out.append(it["id"])
            elif isinstance(it, str):
                out.append(it)
        return sorted(out)

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = 0.3,
        max_tokens: int | None = 4096,
        timeout: float = 180.0,
        retries: int = 2,
        params: dict[str, Any] | None = None,
    ) -> Reply:
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        payload.update(params or {})

        started = time.monotonic()
        attempt = 0
        last = ""
        while attempt <= retries:
            attempt += 1
            try:
                resp = self._request("/chat/completions", payload, timeout)
                body = json.loads(resp.read().decode())
                return self._parse(body, started, attempt)
            except ProviderError as e:
                last = str(e)
                # 400 por parametro nao suportado: remove e tenta de novo (uma vez por parametro).
                if e.status == 400:
                    dropped = _drop_offending_param(payload, e.body)
                    if dropped:
                        last = f"{last} [removido parametro '{dropped}' e repetido]"
                        continue
                    break
                if e.status is not None and e.status not in RETRY_STATUS:
                    break
                if attempt <= retries:
                    time.sleep(min(2 ** attempt, 8))
        return Reply(
            ok=False,
            error=last or "falha desconhecida",
            latency_s=time.monotonic() - started,
            attempts=attempt,
        )

    def stream(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = 0.3,
        max_tokens: int | None = 4096,
        timeout: float = 180.0,
        params: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        payload: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        payload.update(params or {})
        try:
            resp = self._request("/chat/completions", payload, timeout)
        except ProviderError as e:
            yield f"[erro: {e}]"
            return
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            chunk = line[5:].strip()
            if chunk == "[DONE]":
                break
            try:
                delta = json.loads(chunk)["choices"][0].get("delta", {})
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
            piece = delta.get("content")
            if piece:
                yield piece

    # ------------------------------------------------------------------ parse

    @staticmethod
    def _parse(body: dict, started: float, attempt: int) -> Reply:
        choices = body.get("choices") or []
        if not choices:
            err = body.get("error") or body
            return Reply(
                ok=False,
                error=f"resposta sem choices: {json.dumps(err)[:300]}",
                latency_s=time.monotonic() - started,
                attempts=attempt,
            )
        msg = choices[0].get("message") or {}
        content = (msg.get("content") or "").strip()
        reasoning = (msg.get("reasoning_content") or msg.get("reasoning") or "") or ""
        u = body.get("usage") or {}
        usage = Usage(
            prompt_tokens=int(u.get("prompt_tokens") or 0),
            completion_tokens=int(u.get("completion_tokens") or 0),
        )
        if not content:
            finish = choices[0].get("finish_reason", "?")
            return Reply(
                ok=False,
                error=f"conteudo vazio (finish_reason={finish})",
                reasoning=reasoning,
                usage=usage,
                latency_s=time.monotonic() - started,
                attempts=attempt,
            )
        return Reply(
            ok=True,
            content=content,
            reasoning=reasoning,
            usage=usage,
            latency_s=time.monotonic() - started,
            attempts=attempt,
        )


_ADAPTABLE = ("temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty")


def _drop_offending_param(payload: dict, body: str) -> str | None:
    """Alguns modelos (raciocinio) rejeitam temperature/max_tokens. Detecta e remove."""
    low = body.lower()
    if "max_tokens" in payload and "max_completion_tokens" in low:
        payload["max_completion_tokens"] = payload.pop("max_tokens")
        return "max_tokens->max_completion_tokens"
    for p in _ADAPTABLE:
        if p in payload and p in low and ("unsupported" in low or "not support" in low or "invalid" in low):
            payload.pop(p)
            return p
    return None
