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
from .engine import Council, Deliberation, save_run

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
    {
        "name": "council_deliberate",
        "description": (
            "Submete uma DELIBERACAO a um conselho com perfil: conselheiros podem ter "
            "papeis, recebem um bundle de evidencia, produzem candidatos que sao "
            "avaliados as cegas, e o presidente devolve uma decisao estruturada "
            "(status DECIDIDO/ENCALHADO, escolha, confianca, dissidencias, fundamentos) "
            "ou uma sintese, conforme o perfil. Use para decisao de continuidade de "
            "plano (proximo passo apos uma execucao), gates antes de acoes de risco, ou "
            "rodadas de interrogatorio (perfil grill). Nao use para perguntas triviais, "
            "de baixa aposta ou sensiveis a latencia — para isso existe council_ask. O "
            "servidor nao guarda estado: passe bundle e run_refs (shas de deliberacoes "
            "anteriores) em toda chamada de continuidade."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "A pergunta da deliberacao, autocontida.",
                },
                "profile": {
                    "type": "string",
                    "description": "Nome do perfil em [profiles] do council.toml (ex.: continuation, grill).",
                },
                "bundle": {
                    "type": "string",
                    "description": "Opcional: evidencia da deliberacao (plano, resultado da execucao, contexto). O conteudo entra no registro como sha256.",
                },
                "run_refs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Opcional: prefixos de sha256 de deliberacoes anteriores desta cadeia.",
                },
                "members": {
                    "type": "string",
                    "description": "Opcional: nomes de conselheiros separados por virgula, para limitar o conselho.",
                },
            },
            "required": ["question", "profile"],
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


def tool_deliberate(args: dict) -> str:
    cfg = cfgmod.load()
    nome = args.get("profile") or ""
    perfil = cfg.profiles.get(nome)
    if perfil is None:
        disponiveis = ", ".join(sorted(cfg.profiles)) or "(nenhum definido no council.toml)"
        raise Ferramenta(f"perfil '{nome}' nao existe. Disponiveis: {disponiveis}")

    question = args.get("question") or ""
    if not question.strip():
        raise Ferramenta("pergunta vazia — a deliberacao precisa de uma pergunta")

    if args.get("members"):
        wanted = {n.strip() for n in args["members"].split(",")}
        picked = [m for m in cfg.members if m.name in wanted]
        if not picked:
            raise Ferramenta(
                f"members nao casa nenhum conselheiro (pedidos: {sorted(wanted)}; "
                f"disponiveis: {sorted(m.name for m in cfg.members)})"
            )
        cfg.members = picked

    refs: list[str] = []
    if "run_refs" in args:
        crus = args["run_refs"]
        if not isinstance(crus, list) or not all(isinstance(x, str) and x.strip() for x in crus):
            raise Ferramenta("run_refs deve ser uma lista de prefixos de sha256 nao vazios")
        runs_dir = Path(cfg.settings.runs_dir)
        if not runs_dir.is_absolute():
            runs_dir = cfg.source.parent / runs_dir
        registros = sorted(runs_dir.glob("*.json")) if runs_dir.is_dir() else []
        for prefixo in crus:
            casa = []
            for p in registros:
                r = json.loads(p.read_text(encoding="utf-8"))
                if (r.get("sha256") or "").startswith(prefixo):
                    casa.append(r)
            if not casa:
                raise Ferramenta(f"run_refs '{prefixo}' nao casa nenhum registro em {runs_dir}")
            refs.append(max(casa, key=lambda r: r.get("started_at", ""))["sha256"])

    council = Council(cfg, progress=lambda s, m: _log(f"{s}: {m}"))
    rec = council.run(Deliberation(question, profile=perfil,
                                   bundle=args.get("bundle"), run_refs=refs))
    runs_dir = Path(cfg.settings.runs_dir)
    if not runs_dir.is_absolute():
        runs_dir = cfg.source.parent / runs_dir
    try:
        path = save_run(rec, runs_dir)
        registro = path.name
    except OSError as e:
        rec.warnings.append(f"registro nao salvo: {e}")
        registro = ""

    out: dict[str, Any] = {
        "pergunta": rec.question,
        "perfil": rec.profile_name,
        "conselheiros": [m["name"] for m in rec.members],
        "candidates": [{"id": c["id"], "author": c["author"]} for c in rec.candidates],
        "consensus": [
            {"candidato": c["member"], "score": c["score"], "dispersao": c["spread"]}
            for c in rec.consensus if c.get("ballots")
        ],
        "decision": rec.decision,
        "sintese": rec.synthesis.get("content", ""),
        "dividido": rec.divided,
        "avisos": rec.warnings,
        "bundle_sha256": rec.bundle_sha256,
        "run_refs": rec.run_refs,
        "tokens": rec.usage,
        "sha256": rec.digest(),
        "registro": registro,
    }
    return json.dumps(out, ensure_ascii=False, indent=2)


class Ferramenta(Exception):
    """Erro nomeado da ferramenta: vira conteudo isError, nao derruba o servidor."""


HANDLERS = {"council_ask": tool_ask, "council_debate": tool_debate,
            "council_deliberate": tool_deliberate}


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
