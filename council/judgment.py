"""Julgamento cego do operador sobre um registro, e a taxa de concordancia.

O conselho afirma qualidade por voto dos pares. Nada nunca conferiu esse voto
contra o unico juiz que decide de fato. Este modulo produz esse dado: mostra
duas respostas sem autoria e sem o consenso, guarda a escolha endereçada ao
sha256 do registro, e acumula a concordancia entre o operador e o Borda.

O registro selado NAO e alterado — o veredito vive em arquivo proprio que
aponta para o hash dele, do mesmo jeito que uma decisao aponta para o artefato.

Modulo folha: nao importa nada do projeto alem de ranking (cegamento) e runs
(o que e parcial e o que e registro).
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ranking import identity_terms, scrub_identity
from .runs import final_runs

ESCOLHAS = ("1", "2", "empate", "nenhuma")


class SemPar(Exception):
    """Registro nao tem duas respostas comparaveis."""


class JaJulgado(Exception):
    """Ja existe veredito para este registro. Sobrescrever em silencio apagaria
    um julgamento do operador — exige gesto explicito."""


@dataclass
class _Membro:
    """Forma minima que identity_terms espera, reconstruida a partir do registro."""
    name: str
    provider: str
    model: str


def carregar(runs_dir: Path, prefixo: str | None = None) -> tuple[Path, dict[str, Any]]:
    arquivos = final_runs(runs_dir)
    if not arquivos:
        raise SemPar(f"nenhum registro em {runs_dir}")
    if prefixo:
        casa = [f for f in arquivos if prefixo in f.name]
        if not casa:
            raise SemPar(f"nenhum registro casa com '{prefixo}'")
        alvo = casa[-1]
    else:
        alvo = arquivos[-1]
    return alvo, json.loads(alvo.read_text(encoding="utf-8"))


def respostas_validas(rec: dict) -> dict[str, str]:
    return {s["name"]: s["content"] for s in rec.get("stage1", []) if s.get("ok") and s.get("content")}


def escolher_par(rec: dict, explicito: str | None = None) -> tuple[str, str, str]:
    """Por padrao, os dois primeiros do Borda — e ali que a margem decide.

    Comparar o topo com o ultimo seria facil e diria pouco: o teste util e no
    ponto em que o consenso afirma uma diferenca pequena.
    """
    validas = respostas_validas(rec)
    if explicito:
        nomes = [n.strip() for n in explicito.split(",")]
        if len(nomes) != 2:
            raise SemPar("--par exige exatamente dois nomes, separados por virgula")
        for n in nomes:
            if n not in validas:
                raise SemPar(f"'{n}' nao tem resposta valida neste registro (tem: {sorted(validas)})")
        return nomes[0], nomes[1], "par escolhido na linha de comando"

    ranqueados = [c["member"] for c in rec.get("consensus", []) if c.get("ballots") and c["member"] in validas]
    if len(ranqueados) >= 2:
        return ranqueados[0], ranqueados[1], "os dois primeiros do consenso — onde a margem decide"
    if len(validas) >= 2:
        dois = sorted(validas)[:2]
        return dois[0], dois[1], "sem consenso no registro; par arbitrario"
    raise SemPar("registro nao tem duas respostas validas para comparar")


def cegar(rec: dict, par: tuple[str, str], rng: random.Random) -> tuple[list[dict], dict[str, str]]:
    """Devolve as duas opcoes ja mascaradas e em ordem sorteada.

    Sortear a ordem e essencial: se a opcao 1 fosse sempre a favorita do Borda,
    o operador aprenderia o padrao e o teste deixaria de medir qualquer coisa.
    """
    validas = respostas_validas(rec)
    membros = [_Membro(m["name"], m["provider"], m["model"]) for m in rec.get("members", [])]
    termos = identity_terms(membros)
    pergunta = rec.get("question", "")

    ordem = list(par)
    rng.shuffle(ordem)
    opcoes = []
    for i, nome in enumerate(ordem, start=1):
        texto, _ = scrub_identity(validas[nome], termos, pergunta)
        opcoes.append({"slot": str(i), "texto": texto})
    slot_para_membro = {str(i): nome for i, nome in enumerate(ordem, start=1)}
    return opcoes, slot_para_membro


def consenso_de(rec: dict, nome: str) -> float | None:
    for c in rec.get("consensus", []):
        if c["member"] == nome:
            return c["score"]
    return None


def concorda(rec: dict, escolhido: str, outro: str) -> bool | None:
    """A escolha do operador bate com quem o Borda pos na frente?"""
    a, b = consenso_de(rec, escolhido), consenso_de(rec, outro)
    if a is None or b is None or a == b:
        return None
    return a > b


def gravar(
    dir_vereditos: Path,
    caminho_registro: Path,
    rec: dict,
    slot_para_membro: dict[str, str],
    escolha: str,
    nota: str,
    selo: dict,
    refazer: bool = False,
) -> tuple[Path, dict]:
    dir_vereditos.mkdir(parents=True, exist_ok=True)
    run_sha = rec.get("sha256", "")

    destino = dir_vereditos / f"{run_sha[:12]}-ab.json"
    anterior = None
    if destino.is_file():
        anterior = json.loads(destino.read_text(encoding="utf-8"))
        if not refazer:
            raise JaJulgado(
                f"ja existe veredito para este registro em {destino.name} "
                f"(escolha '{anterior.get('escolha')}', em {anterior.get('em')}). "
                f"Use --redo para substituir; o veredito anterior fica guardado dentro do novo."
            )

    escolhido = slot_para_membro.get(escolha) if escolha in ("1", "2") else None
    outro = next((v for k, v in slot_para_membro.items() if v != escolhido), None) if escolhido else None

    veredito = {
        "tipo": "ab-cego",
        "registro_sha256": run_sha,
        "registro_arquivo": caminho_registro.name,
        "pergunta": rec.get("question", "")[:400],
        "apresentado": slot_para_membro,
        "escolha": escolha,
        "escolhido": escolhido,
        "preterido": outro,
        # verbatim do operador, digitado direto no comando — nao transcrito por agente
        "nota": nota,
        "consenso": {n: consenso_de(rec, n) for n in slot_para_membro.values()},
        "concorda_com_borda": concorda(rec, escolhido, outro) if escolhido and outro else None,
        "em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "julgado_por": selo,
        # substituir um veredito nao apaga o anterior: ele vem junto, encadeado
        "substitui": {k: v for k, v in anterior.items() if k != "substitui"} if anterior else None,
    }
    blob = json.dumps(veredito, sort_keys=True, ensure_ascii=False).encode()
    veredito["sha256"] = hashlib.sha256(blob).hexdigest()

    destino.write_text(json.dumps(veredito, ensure_ascii=False, indent=2), encoding="utf-8")
    return destino, veredito


def apurar(dir_vereditos: Path) -> dict[str, Any]:
    """Taxa de concordancia entre o operador cego e o Borda."""
    arquivos = sorted(dir_vereditos.glob("*-ab.json")) if dir_vereditos.is_dir() else []
    vereditos = [json.loads(f.read_text(encoding="utf-8")) for f in arquivos]
    decididos = [v for v in vereditos if v.get("concorda_com_borda") is not None]
    acordos = [v for v in decididos if v["concorda_com_borda"]]
    return {
        "total": len(vereditos),
        "decididos": len(decididos),
        "acordos": len(acordos),
        "empates_ou_abstencoes": len(vereditos) - len(decididos),
        "taxa": (len(acordos) / len(decididos)) if decididos else None,
        "vereditos": vereditos,
    }
