"""Custo derivado dos registros: ledger acumulado e pre-voo de chamadas.

Modulo folha (so stdlib, sem rede, nao importa engine): o gasto ja foi
pago e gravado — aqui ele e somado e estimado, nunca inventado. Registro
antigo (pre-C2, sem usage_by_stage) entra com subcontagem nomeada: as
cedulas contam como chamadas, os tokens do estagio 2 nao existiam la.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from .config import Config
from .runs import PARTIAL_SUFFIX, final_runs

_ZERADO = {"chamadas": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


class SemHistorico(Exception):
    """Estimativa impossivel: estagio sem nenhuma chamada com usage observada."""


def _mediana(amostras: list[dict[str, int]]) -> dict[str, int | float]:
    # total e derivado (prompt + completion): medianas independentes poderiam
    # produzir total != prompt + completion e a soma deixaria de fechar
    prompt = statistics.median(a["prompt_tokens"] for a in amostras)
    completion = statistics.median(a["completion_tokens"] for a in amostras)
    return {"prompt_tokens": prompt, "completion_tokens": completion,
            "total_tokens": prompt + completion}


def ledger(runs_dir: Path) -> dict[str, Any]:
    """Acumula por provedor/modelo, registro final e parcial separados.

    Contagem de chamadas: estagio 1 e synthesis contam por entrada (falha
    com usage e gasto pago); cedula conta quando tem usage — None e "nao
    houve chamada" (C2). Registro pre-C2: cedula e chamada, tokens do
    estagio 2 subcontados com nota nomeada.
    """
    registros = {"finais": 0, "parciais": 0, "antigos_sem_usage_by_stage": 0}
    por_pm: dict[tuple[str, str], dict[str, Any]] = {}
    notas: list[str] = []

    def conta(provider: str, model: str, parcial: bool,
              usage: dict[str, int] | None) -> None:
        balde = por_pm.setdefault((provider, model),
                                  {"final": dict(_ZERADO), "parcial": dict(_ZERADO)})[
            "parcial" if parcial else "final"]
        balde["chamadas"] += 1
        if usage:
            for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                balde[k] += usage.get(k, 0)

    files = sorted(runs_dir.glob("*.json")) if runs_dir.is_dir() else []
    if not files:
        notas.append(f"nenhum registro em {runs_dir}")
    for path in files:
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as e:
            notas.append(f"{path.name}: registro ilegivel — {type(e).__name__}: {e}")
            continue
        parcial = path.name.endswith(PARTIAL_SUFFIX)
        registros["parciais" if parcial else "finais"] += 1
        antigo = not rec.get("usage_by_stage")
        if antigo:
            registros["antigos_sem_usage_by_stage"] += 1
        membros = {m.get("name"): (m.get("provider"), m.get("model"))
                   for m in rec.get("members", [])}
        for e in rec.get("stage1", []):
            conta(e.get("provider"), e.get("model"), parcial, e.get("usage"))
        for b in rec.get("stage2", []):
            par = membros.get(b.get("ranker"))
            if par is None:
                notas.append(f"{path.name}: cedula de '{b.get('ranker')}' sem membro "
                             f"correspondente — fora do ledger")
                continue
            if antigo:
                conta(par[0], par[1], parcial, None)
            elif b.get("usage") is not None:
                conta(par[0], par[1], parcial, b.get("usage"))
        s = rec.get("synthesis") or {}
        if s:
            conta(s.get("provider"), s.get("model"), parcial, s.get("usage"))
        if antigo and rec.get("stage2"):
            notas.append(f"{path.name}: registro anterior a C2 — tokens do estagio 2 "
                         f"nao registrados (subcontagem)")

    por_provedor: dict[str, Any] = {}
    for (provider, model), pm in sorted(por_pm.items()):
        por_provedor.setdefault(provider, {})[model] = pm
    return {"registros": registros, "por_provedor": por_provedor, "notas": notas}


def estimate(cfg: Config, runs_dir: Path, profile: str | None = None) -> dict[str, Any]:
    """Pre-voo da proxima deliberacao: chamadas por provedor derivadas da
    aritmetica da config (membros ativos, com chave); tokens = medianas por
    estagio dos registros finais. Sem historia para algum estagio da
    estimativa: SemHistorico — zero numero inventado."""
    membros = cfg.active_members()
    n = len(membros)
    roda_stage2 = n >= 3

    chamadas: dict[str, dict[str, int]] = {}

    def add(provider: str, estagio: str) -> None:
        chamadas.setdefault(provider, {"stage1": 0, "stage2": 0, "synthesis": 0})
        chamadas[provider][estagio] += 1

    for m in membros:
        add(m.provider, "stage1")
    if roda_stage2:
        for m in membros:
            add(m.provider, "stage2")
    add(cfg.chairman.provider, "synthesis")

    amostras: dict[str, list[dict[str, int]]] = {"stage1": [], "stage2": [], "synthesis": []}
    historicos = 0
    notas: list[str] = []
    for p in final_runs(runs_dir):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as e:
            notas.append(f"{p.name}: registro ilegivel fora das medianas — "
                         f"{type(e).__name__}: {e}")
            continue
        historicos += 1
        for e in rec.get("stage1", []):
            if e.get("usage"):
                amostras["stage1"].append(e["usage"])
        if rec.get("usage_by_stage"):
            for b in rec.get("stage2", []):
                if b.get("usage") is not None:
                    amostras["stage2"].append(b["usage"])
        s = rec.get("synthesis") or {}
        if s.get("usage"):
            amostras["synthesis"].append(s["usage"])

    precisos = [e for e, amo in amostras.items() if (e != "stage2" or roda_stage2) and not amo]
    if precisos:
        raise SemHistorico(
            f"estagio(s) {', '.join(precisos)} sem nenhuma chamada com usage em "
            f"{runs_dir} (registros finais: {historicos})")

    medianas = {e: _mediana(amo) for e, amo in amostras.items() if amo}

    tokens: dict[str, dict[str, int | float]] = {}
    for provider, c in chamadas.items():
        t: dict[str, int | float] = {"prompt_tokens": 0, "completion_tokens": 0,
                                     "total_tokens": 0}
        for estagio, qtd in c.items():
            if qtd and medianas.get(estagio):
                for k in t:
                    t[k] += qtd * medianas[estagio][k]
        tokens[provider] = t

    suposicoes = ["todos os membros respondem no estagio 1"]
    if roda_stage2:
        suposicoes.append(
            f"com {n} membros, cada respondente destila ao menos 1 candidato valido "
            f"e o estagio 2 roda: 1 cedula por respondente (auto-exclusao nao muda o n de chamadas)")
    else:
        suposicoes.append(f"com {n} membros o estagio 2 e pulado (menos de 3 candidatos)")
    suposicoes.append("presidente faz 1 chamada no caminho normal (sem impasse de decisor)")

    return {
        "membros": n,
        "perfil": profile,
        "suposicoes": suposicoes,
        "chamadas_por_provedor": {
            provider: {**c, "total": sum(c.values())} for provider, c in chamadas.items()},
        "medianas_por_estagio": medianas,
        "tokens_estimados_por_provedor": tokens,
        "registros_historicos": historicos,
        "notas": notas,
    }
