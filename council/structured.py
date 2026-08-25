"""Parser estruturado das saidas de deliberacao: QUESTIONS, PROPOSAL, DECISION.

Modulo folha de proposito: nao importa nada do projeto, roda em qualquer
python com stdlib. A filosofia e a do parser de cedulas (ranking.py):
tolerante a variacao real de formato (negrito, cabecalho traduzido,
minusculo), mas nunca inventa — bloco ausente ou ilegivel devolve erro
nomeado e resultado vazio, nunca um campo adivinhado.

Contrato: toda funcao devolve (resultado, erro); erro == "" significa
sucesso; resultado vazio com erro nomeado significa falha explicita.
"""

from __future__ import annotations

import re
from typing import Any

# Cabetalhos aceitos, em qualquer lingua que o modelo resolve produzir.
_QUESTION_HEADERS = ("QUESTIONS", "QUSTIONS", "QUESTOES", "PERGUNTAS")
_PROPOSAL_HEADERS = ("PROPOSAL", "PROPOSTA")
_DECISION_HEADERS = ("DECISION", "DECISAO")

_STATUS_VALIDOS = ("DECIDIDO", "ENCALHADO")


def _section(texto: str, headers: tuple[str, ...]) -> str | None:
    """Trecho apos o ultimo cabecalho reconhecido (padrao do ranking.py)."""
    up = texto.upper()
    best, end = -1, 0
    for h in headers:
        idx = up.rfind(h)
        if idx > best:
            best, end = idx, idx + len(h)
    return texto[end:] if best >= 0 else None


def _limpar(campo: str) -> str:
    return campo.strip().strip("*_`\"'").strip()


# N | pergunta | recomendacao  (numero com marcadores markdown tolerados)
_QUESTION_LINE = re.compile(
    r"^\s*[*_`]*\s*(\d+)\s*[.)\-]?\s*[*_`]*\s*\|\s*(.*?)\s*\|\s*(.*?)\s*$",
    re.MULTILINE,
)


def parse_questions(texto: str, max_n: int) -> tuple[list[dict[str, Any]], str]:
    """Linhas `N | pergunta | recomendacao` do bloco QUESTIONS:.

    Ids fora de 1..max_n sao ignorados (o mesmo tratamento que o parser de
    verificacao da ao indice fora do intervalo). Linha sem o segundo pipe e
    linha destruida, nao questao incompleta: fica de fora.
    """
    sec = _section(texto, _QUESTION_HEADERS)
    if sec is None:
        return [], "bloco QUESTIONS ausente"
    questoes: list[dict[str, Any]] = []
    vistos: set[int] = set()
    for m in _QUESTION_LINE.finditer(sec):
        n = int(m.group(1))
        if not (1 <= n <= max_n) or n in vistos:
            continue
        vistos.add(n)
        questoes.append({"id": str(n), "pergunta": m.group(2), "recomendacao": m.group(3)})
    if not questoes:
        return [], "nenhuma linha de questao reconhecida no bloco QUESTIONS"
    return questoes, ""


def parse_proposal(texto: str) -> tuple[dict[str, Any], str]:
    """Campos TITULO: e CORPO: do bloco PROPOSAL:.

    O corpo e tudo que vem apos a linha TITULO ate o fim do bloco — a
    proposta e multi-linha por natureza.
    """
    sec = _section(texto, _PROPOSAL_HEADERS)
    if sec is None:
        return {}, "bloco PROPOSAL ausente"
    m = re.search(r"^\s*[*_`]*\s*T[ÍI]TULO\s*[:\-]?\s*[*_`]*\s*(.*)$", sec,
                  re.IGNORECASE | re.MULTILINE)
    if not m:
        return {}, "campo TITULO ausente no bloco PROPOSAL"
    titulo = _limpar(m.group(1))
    c = re.search(r"^\s*[*_`]*\s*CORPO\s*[:\-]?\s*[*_`]*\s*(.*)$",
                  sec[m.end():], re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if not c:
        return {}, "campo CORPO ausente no bloco PROPOSAL"
    corpo = c.group(1).strip().strip("*_`").strip()
    return {"titulo": titulo, "corpo": corpo}, ""


def parse_decision(texto: str, ids_validos: list[str]) -> tuple[dict[str, Any], str]:
    """Linha `STATUS | ESCOLHA | CONFIANCA | DISSIDENCIAS | FUNDAMENTOS` do
    bloco DECISION:.

    Pipes extras alem do quinto campo pertencem ao ultimo campo (fundamentos
    e texto livre). Prosa ao redor da linha e ignorada — nunca interpretada.
    """
    sec = _section(texto, _DECISION_HEADERS)
    if sec is None:
        return {}, "bloco DECISION ausente"
    for linha in sec.splitlines():
        partes = linha.split("|")
        if len(partes) < 5 or not any(p.strip() for p in partes[1:]):
            continue
        status = _limpar(partes[0]).upper().rstrip(".!")
        escolha = _limpar(partes[1])
        confianca = _limpar(partes[2])
        dissidencias = _limpar(partes[3])
        fundamentos = "|".join(partes[4:]).strip()
        if status not in _STATUS_VALIDOS:
            return {}, f"status invalido: '{status}' (use {' ou '.join(_STATUS_VALIDOS)})"
        if escolha not in ids_validos:
            return {}, f"escolha '{escolha}' fora dos ids validos ({sorted(ids_validos)})"
        return {
            "status": status,
            "escolha": escolha,
            "confianca": confianca,
            "dissidencias": dissidencias,
            "fundamentos": fundamentos,
        }, ""
    return {}, "nenhuma linha de decisao reconhecida no bloco DECISION"
