"""Servidor MCP (stdio, JSON-RPC delimitado por linha). Sem dependencias.

Registre no Claude Code com:
    claude mcp add council -- python3 -m council.mcp_server
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import config as cfgmod
from .engine import Council, save_run

PROTOCOL = "2024-11-05"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "council_ask",
        "description": (
            "Submete uma pergunta a um conselho de LLMs de provedores diferentes e devolve UMA "
            "resposta final sintetizada. Cada conselheiro responde de forma independente, depois "
            "avalia as respostas dos outros as cegas (sem saber quem escreveu, sem avaliar a "
            "propria, com a ordem embaralhada por avaliador), e um presidente sintetiza usando o "
            "ranking agregado. Use quando a pergunta for dificil, contestavel ou cara de errar e "
            "valer a pena gastar varios modelos e ~1 minuto para reduzir o risco de uma resposta "
            "unica errada. Nao use para tarefas triviais, de baixa aposta ou sensiveis a latencia."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "A pergunta ou tarefa, autocontida — o conselho nao ve esta conversa.",
                },
                "members": {
                    "type": "string",
                    "description": "Opcional: nomes de conselheiros separados por virgula, para limitar o conselho.",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "council_debate",
        "description": (
            "Igual ao council_ask, mas devolve o material bruto em vez de so a sintese: a resposta "
            "de cada conselheiro, a tabela de consenso (Borda normalizado, posicoes e dispersao), o "
            "ponto forte e a falha que cada avaliador cego apontou, os avisos de falha, e a sintese "
            "final. Use quando importar ONDE os modelos discordam — nao apenas qual e a resposta."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "A pergunta, autocontida."},
                "include_full_answers": {
                    "type": "boolean",
                    "description": "Incluir o texto completo de cada conselheiro (default: false, so um resumo).",
                },
            },
            "required": ["question"],
        },
    },
]


def _log(msg: str) -> None:
    print(f"[council-mcp] {msg}", file=sys.stderr, flush=True)


def _run_council(question: str, members: str | None = None):
    cfg = cfgmod.load()
    if members:
        wanted = {n.strip() for n in members.split(",")}
        picked = [m for m in cfg.members if m.name in wanted]
        if picked:
            cfg.members = picked
    council = Council(cfg, progress=lambda s, m: _log(f"{s}: {m}"))
    rec = council.run(question)
    runs_dir = Path(cfg.settings.runs_dir)
    if not runs_dir.is_absolute():
        runs_dir = cfg.source.parent / runs_dir
    try:
        save_run(rec, runs_dir)
    except OSError as e:
        rec.warnings.append(f"registro nao salvo: {e}")
    return rec


def tool_ask(args: dict) -> str:
    rec = _run_council(args["question"], args.get("members"))
    body = rec.synthesis.get("content") or "(o conselho nao produziu sintese)"
    tail = []
    if rec.divided:
        tail.append("Conselho dividido: os avaliadores nao convergiram; trate como uma opcao, nao consenso.")
    tail += [f"aviso: {w}" for w in rec.warnings]
    if tail:
        body += "\n\n---\n" + "\n".join(tail)
    return body


def tool_debate(args: dict) -> str:
    rec = _run_council(args["question"])
    full = bool(args.get("include_full_answers"))
    out: dict[str, Any] = {
        "pergunta": rec.question,
        "conselheiros": [m["name"] for m in rec.members],
        "consenso": [
            {
                "conselheiro": c["member"],
                "score": c["score"],
                "posicoes": c["positions"],
                "dispersao": c["spread"],
                "a_favor": c["strengths"][:3],
                "contra": c["weaknesses"][:3],
            }
            for c in rec.consensus
        ],
        "cedulas": [
            {"avaliador": b["ranker"], "ordem": b["order_members"], "erro": b["error"]}
            for b in rec.stage2
        ],
        "dividido": rec.divided,
        "avisos": rec.warnings,
        "sintese": rec.synthesis.get("content", ""),
        "tokens": rec.usage,
        "sha256": rec.digest(),
    }
    if full:
        out["respostas"] = {
            s["name"]: s["content"] for s in rec.stage1 if s.get("ok")
        }
    else:
        out["respostas_resumo"] = {
            s["name"]: (s["content"][:400] + "…" if len(s["content"]) > 400 else s["content"])
            for s in rec.stage1
            if s.get("ok")
        }
    return json.dumps(out, ensure_ascii=False, indent=2)


HANDLERS = {"council_ask": tool_ask, "council_debate": tool_debate}


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        return _ok(mid, {
            "protocolVersion": PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "llm-council", "version": "0.1.0"},
        })
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return _ok(mid, {})
    if method == "tools/list":
        return _ok(mid, {"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        fn = HANDLERS.get(name)
        if fn is None:
            return _err(mid, -32602, f"ferramenta desconhecida: {name}")
        try:
            text = fn(params.get("arguments") or {})
            return _ok(mid, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as e:  # devolve o erro como conteudo, nunca derruba o servidor
            _log(f"erro em {name}: {type(e).__name__}: {e}")
            return _ok(mid, {
                "content": [{"type": "text", "text": f"falha do conselho: {type(e).__name__}: {e}"}],
                "isError": True,
            })
    if mid is None:
        return None
    return _err(mid, -32601, f"metodo nao suportado: {method}")


def _ok(mid, result) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _err(mid, code, message) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve() -> int:
    _log("pronto (stdio)")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _log("json invalido, ignorado")
            continue
        try:
            resp = handle(msg)
        except Exception as e:
            _log(f"erro no dispatch: {e}")
            resp = _err(msg.get("id"), -32603, str(e))
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(serve())
