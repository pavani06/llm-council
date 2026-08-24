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
    finish: str = ""
    request_id: str = ""

    @property
    def truncated(self) -> bool:
        # 'length' nos OpenAI-compativeis, 'max_tokens' na Messages API da Anthropic.
        return self.finish in ("length", "max_tokens")

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "content": self.content,
            "reasoning": self.reasoning,
            "error": self.error,
            "usage": self.usage.as_dict(),
            "latency_s": round(self.latency_s, 2),
            "attempts": self.attempts,
            "finish": self.finish,
            "request_id": self.request_id,
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
        finish = choices[0].get("finish_reason") or ""
        content = (msg.get("content") or "").strip()
        reasoning = (msg.get("reasoning_content") or msg.get("reasoning") or "") or ""
        u = body.get("usage") or {}
        usage = Usage(
            prompt_tokens=int(u.get("prompt_tokens") or 0),
            completion_tokens=int(u.get("completion_tokens") or 0),
        )
        if not content:
            extra = " — o modelo gastou o teto raciocinando" if finish == "length" else ""
            return Reply(
                ok=False,
                finish=finish,
                error=f"conteudo vazio (finish_reason={finish}){extra}",
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
            finish=finish,
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


class AnthropicEndpoint(Endpoint):
    """Anthropic Messages API pelo SDK oficial (`anthropic`).

    Unico provedor com dependencia externa; os outros tres seguem stdlib pura.
    O SDK cuida de auth, versionamento de API, retries com backoff e tipos de erro —
    nao reimplementar nada disso aqui.

    O que ainda precisa de cuidado nosso:
    - `temperature` foi REMOVIDA nos modelos atuais (Opus 5, Sonnet 5, 4.7/4.8): mandar
      devolve 400. So vai se o operador pedir explicitamente em [params].
    - `thinking` fica omitido de proposito: no Opus 5 omitir ja significa adaptativo, e
      mandar `{type: "adaptive"}` quebraria num modelo antigo como o Haiku 4.5. Quem
      trocar para Opus 4.8/4.7 (onde omitir = sem raciocinio) declara em [params].
    - a resposta e uma lista de blocos; `thinking` nao e texto de resposta.
    - `stop_reason: "refusal"` chega como sucesso HTTP e precisa virar falha explicita.
    - truncamento aqui e `stop_reason: "max_tokens"`, nao "length".
    """

    def _client(self, timeout: float, retries: int):
        try:
            import anthropic
        except ImportError:
            raise ProviderError(
                None,
                "SDK 'anthropic' ausente. Instale no venv do projeto: "
                ".venv/bin/python -m pip install anthropic",
            ) from None
        kwargs: dict[str, Any] = {"timeout": timeout, "max_retries": retries}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self.extra_headers:
            kwargs["default_headers"] = self.extra_headers
        return anthropic.Anthropic(**kwargs)

    @staticmethod
    def _split(messages: list[dict[str, str]]) -> tuple[str | None, list[dict[str, str]]]:
        system = None
        turns = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"] if system is None else f"{system}\n\n{m['content']}"
            else:
                turns.append({"role": m["role"], "content": m["content"]})
        return system, turns

    def _build(self, model, messages, max_tokens, params) -> dict[str, Any]:
        system, turns = self._split(messages)
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens or 4096,  # obrigatorio na Messages API
            "messages": turns,
        }
        if system:
            kwargs["system"] = system
        kwargs.update(params or {})  # temperature/thinking entram so por aqui
        return kwargs

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
        started = time.monotonic()
        try:
            client = self._client(timeout, retries)
            resp = client.messages.create(**self._build(model, messages, max_tokens, params))
        except ProviderError as e:
            return Reply(ok=False, error=str(e), latency_s=time.monotonic() - started)
        except Exception as e:
            return Reply(ok=False, error=self._describe(e), latency_s=time.monotonic() - started)
        return self._parse_sdk(resp, started)

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
        try:
            client = self._client(timeout, 2)
            with client.messages.stream(**self._build(model, messages, max_tokens, params)) as s:
                yield from s.text_stream
        except ProviderError as e:
            yield f"[erro: {e}]"
        except Exception as e:
            yield f"[erro: {self._describe(e)}]"

    def list_models(self, timeout: float = 30.0) -> list[str]:
        client = self._client(timeout, 1)
        return sorted(m.id for m in client.models.list())

    @staticmethod
    def _describe(e: Exception) -> str:
        """Cadeia do mais especifico para o mais generico — um except largo perderia
        a diferenca entre o que adianta repetir e o que nao adianta."""
        try:
            import anthropic
        except ImportError:
            return f"{type(e).__name__}: {e}"
        if isinstance(e, anthropic.NotFoundError):
            return f"modelo ou rota inexistente: {e}"
        if isinstance(e, anthropic.AuthenticationError):
            return "chave recusada (CLAUDE_API_KEY)"
        if isinstance(e, anthropic.PermissionDeniedError):
            return "chave sem permissao para este recurso"
        if isinstance(e, anthropic.RateLimitError):
            return f"rate limit persistiu apos os retries do SDK: {e}"
        if isinstance(e, anthropic.APIStatusError):
            return f"HTTP {e.status_code}: {getattr(e, 'message', e)}"
        if isinstance(e, anthropic.APIConnectionError):
            return f"falha de conexao: {e}"
        return f"{type(e).__name__}: {e}"

    @staticmethod
    def _parse_sdk(resp: Any, started: float) -> Reply:
        u = getattr(resp, "usage", None)
        usage = Usage(
            prompt_tokens=int(getattr(u, "input_tokens", 0) or 0),
            completion_tokens=int(getattr(u, "output_tokens", 0) or 0),
        )
        rid = getattr(resp, "_request_id", "") or ""
        stop = getattr(resp, "stop_reason", "") or ""
        elapsed = time.monotonic() - started

        if stop == "refusal":
            det = getattr(resp, "stop_details", None)
            cat = getattr(det, "category", None)
            exp = getattr(det, "explanation", None)
            return Reply(ok=False, usage=usage, finish=stop, request_id=rid, latency_s=elapsed,
                         error=f"recusa do modelo (categoria={cat}): {exp}")

        blocks = getattr(resp, "content", None) or []
        text = "\n".join(b.text for b in blocks if getattr(b, "type", "") == "text").strip()
        thinking = "\n".join(
            getattr(b, "thinking", "") or "" for b in blocks if getattr(b, "type", "") == "thinking"
        ).strip()

        if not text:
            extra = " — o teto foi consumido antes de sair texto" if stop == "max_tokens" else ""
            return Reply(ok=False, usage=usage, reasoning=thinking, finish=stop, request_id=rid,
                         latency_s=elapsed, error=f"sem bloco de texto (stop_reason={stop}){extra}")

        return Reply(ok=True, content=text, reasoning=thinking, usage=usage, finish=stop,
                     request_id=rid, latency_s=elapsed)


ENDPOINT_TYPES = {"openai": Endpoint, "anthropic": AnthropicEndpoint}
