"""Parser estruturado das saidas de deliberacao: QUESTIONS, PROPOSAL, DECISION.

Modulo folha de proposito: nao importa nada do projeto, roda em qualquer
python com stdlib. A filosofia e a do parser de cedulas (ranking.py):
tolerante a variacao real de formato (negrito, cabecalho traduzido,
minusculo, acento), mas nunca inventa — bloco ausente ou ilegivel devolve
erro nomeado e resultado vazio, nunca um campo adivinhado.

Cebecalho so vale como LINHA INTEIRA (possivelmente com ':' e negrito):
'NOTQUESTIONS:' nao abre bloco. A secao termina na proxima linha de
cabecalho estruturado (de qualquer tipo) — corpo de PROPOSAL nao engole
um DECISION posterior, e 'QUESTIONS:' citado dentro de outro bloco nao
sequestra o parse.

Contrato: toda funcao devolve (resultado, erro); erro == "" significa
sucesso; resultado vazio com erro nomeado significa falha explicita.
"""

from __future__ import annotations

import re
from typing import Any

# Cabecalhos aceitos, nas grafias que modelo real produz (com e sem acento).
_QUESTION_HEADERS = ("QUESTIONS", "QUESTOES", "QUESTÕES", "PERGUNTAS")
_PROPOSAL_HEADERS = ("PROPOSAL", "PROPOSTA")
_DECISION_HEADERS = ("DECISION", "DECISAO", "DECISÃO")
_TODOS_HEADERS = _QUESTION_HEADERS + _PROPOSAL_HEADERS + _DECISION_HEADERS

_STATUS_VALIDOS = ("DECIDIDO", "ENCALHADO")


def _normalizar_cabecalho(linha: str) -> str:
    """Tira negrito/sublinhado/crase e dois-pontos finais, em qualquer ordem
    ('**QUESTIONS**:' e 'QUESTIONS::::' viram 'QUESTIONS')."""
    s = linha.strip()
    while True:
        t = s.strip("*_`").strip().rstrip(":").strip()
        if t == s:
            return t
        s = t


def _eh_cabecalho(linha: str, headers: tuple[str, ...]) -> bool:
    return _normalizar_cabecalho(linha).upper() in headers


def _section(texto: str, headers: tuple[str, ...]) -> str | None:
    """Linhas apos o ULTIMO cabecalho procurado, ate o proximo cabecalho
    estruturado de qualquer tipo (ou o fim do texto)."""
    linhas = texto.splitlines()
    fim = -1
    for i, ln in enumerate(linhas):
        if _eh_cabecalho(ln, headers):
            fim = i
    if fim < 0:
        return None
    corpo: list[str] = []
    for ln in linhas[fim + 1:]:
        if _eh_cabecalho(ln, _TODOS_HEADERS):
            break
        corpo.append(ln)
    return "\n".join(corpo)


def _limpar(campo: str) -> str:
    s = campo.strip()
    while True:
        t = s.strip("*_`\"'").strip()
        if t == s:
            return t
        s = t


def _vazio_semantico(campo: str) -> bool:
    """Vazio depois de tirar espaco, aspas e negrito — '\"\"' e '**' nao
    sao conteudo; '-' e 'nenhuma' sao."""
    return not _limpar(campo)


# N | pergunta | recomendacao  (numero com marcadores markdown tolerados;
# limite de 9 digitos porque int() de milhares de digitos lanca ValueError)
_QUESTION_LINE = re.compile(
    r"^\s*[*_`]*\s*(\d{1,9})\s*[.)\-]?\s*[*_`]*\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$",
    re.MULTILINE,
)


def parse_questions(texto: str, max_n: int) -> tuple[list[dict[str, Any]], str]:
    """Linhas `N | pergunta | recomendacao` do bloco QUESTIONS:.

    Ids fora de 1..max_n sao ignorados (o mesmo tratamento que o parser de
    verificacao da ao indice fora do intervalo). Linha sem o segundo pipe,
    ou com campo vazio, e linha destruida — nao vira questao incompleta.
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
        if _vazio_semantico(m.group(2)) or _vazio_semantico(m.group(3)):
            continue
        vistos.add(n)
        questoes.append({"id": str(n), "pergunta": m.group(2).strip(),
                         "recomendacao": m.group(3).strip()})
    if not questoes:
        return [], "nenhuma linha de questao reconhecida no bloco QUESTIONS"
    return questoes, ""


def parse_proposal(texto: str) -> tuple[dict[str, Any], str]:
    """Campos TITULO: e CORPO: do bloco PROPOSAL:.

    O corpo e tudo que vem apos a linha TITULO ate o fim do bloco — a
    proposta e multi-linha por natureza. Campo vazio e malformed, nao
    default.
    """
    sec = _section(texto, _PROPOSAL_HEADERS)
    if sec is None:
        return {}, "bloco PROPOSAL ausente"
    m = re.search(r"^[ \t]*[*_`]*[ \t]*T[ÍI]TULO[ \t]*[:\-]?[ \t]*[*_`]*[ \t]*(.*)$", sec,
                  re.IGNORECASE | re.MULTILINE)
    if not m:
        return {}, "campo TITULO ausente no bloco PROPOSAL"
    titulo = _limpar(m.group(1))
    if not titulo:
        return {}, "campo TITULO vazio no bloco PROPOSAL"
    c = re.search(r"^[ \t]*[*_`]*[ \t]*CORPO[ \t]*[:\-]?[ \t]*[*_`]*[ \t]*(.*)$",
                  sec[m.end():], re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if not c:
        return {}, "campo CORPO ausente no bloco PROPOSAL"
    corpo = _limpar(c.group(1))
    if not corpo:
        return {}, "campo CORPO vazio no bloco PROPOSAL"
    return {"titulo": titulo, "corpo": corpo}, ""


def parse_decision(texto: str, ids_validos: list[str]) -> tuple[dict[str, Any], str]:
    """Linha `STATUS | ESCOLHA | CONFIANCA | DISSIDENCIAS | FUNDAMENTOS` do
    bloco DECISION:.

    Pipes extras alem do quinto campo pertencem ao ultimo campo (fundamentos
    e texto livre). Campo vazio invalida a linha; prosa ao redor nunca e
    interpretada como decisao.
    """
    sec = _section(texto, _DECISION_HEADERS)
    if sec is None:
        return {}, "bloco DECISION ausente"
    for linha in sec.splitlines():
        partes = linha.split("|")
        if len(partes) < 5:
            continue
        status = _limpar(partes[0])
        escolha = _limpar(partes[1])
        confianca = _limpar(partes[2])
        dissidencias = _limpar(partes[3])
        fundamentos = "|".join(partes[4:]).strip()
        if (_vazio_semantico(status) or _vazio_semantico(escolha)
                or _vazio_semantico(confianca) or _vazio_semantico(dissidencias)
                or _vazio_semantico(fundamentos)):
            continue
        status = status.upper().rstrip(".!")
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
