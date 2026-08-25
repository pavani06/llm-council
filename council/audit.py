"""Audita a sintese contra o que o conselho de fato sustentou.

O presidente recebe as respostas e devolve texto novo. Nada verificava que ele
so afirma o que os membros sustentaram — ele pode contrabandear.

Duas ressalvas que definem o desenho:

1. Sobreposicao lexical NAO e sustentacao. Uma sintese boa parafraseia, entao
   frase com pouca sobreposicao pode estar perfeitamente sustentada. Por isso a
   varredura offline nao pontua frases: ela procura TERMOS ESPECIFICOS — numero,
   sigla, identificador, nome proprio — que nao aparecem em resposta nenhuma.
   Contrabando se parece com isso: um numero que ninguem citou, um nome que
   ninguem mencionou. Palavra comum e ruido e fica de fora.

2. O proprio prompt do presidente MANDA corrigir o conselho quando ele erra em
   bloco. Entao acrescimo nem sempre e falha — as vezes e a correcao pedida. Esta
   varredura mostra o que ele acrescentou por conta propria; quem julga e o
   operador.

Modulo folha: nao importa nada do projeto.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

# Palavras comuns nao carregam sustentacao — se entrassem, tudo viraria alarme.
_VAZIAS = {
    "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das", "em", "no", "na",
    "nos", "nas", "por", "para", "com", "sem", "que", "e", "ou", "mas", "se", "ao", "aos",
    "the", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are", "be", "as",
    "isso", "isto", "esse", "essa", "este", "esta", "quando", "onde", "como", "porque",
    "mais", "menos", "muito", "pouco", "todo", "toda", "todos", "todas", "ser", "ter",
    "pode", "podem", "deve", "devem", "sao", "esta", "estao", "foi", "foram", "seu", "sua",
    "nao", "sim", "ja", "entre", "sobre", "apenas", "tambem", "cada", "qual", "quais",
}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalizar(texto: str) -> str:
    return _sem_acento(texto).lower()


# Um termo e "especifico" quando carrega compromisso factual conferivel.
# Calibrado contra os registros reais: a regra "palavra longa" foi REMOVIDA porque
# sinalizava 185 de 188 termos — sinonimo de parafrase, nao contrabando. Sobra o
# que o presidente nao poderia ter inventado sem afirmar algo novo.
_NUMERO = re.compile(r"\b\d+(?:[.,]\d+)?\s*%?\b")
_CODIGO = re.compile(
    r"`([^`\n]+)`"                     # trecho em crase, uma linha so
    r"|\b[a-z]+_[a-z_]+\b"             # snake_case
    r"|\b[a-z]+\.[a-zA-Z][a-zA-Z0-9_]+\b"   # dotted.path
    r"|\b[A-Z]{2,}(?:_[A-Z0-9]+)*\b"   # SIGLA / CONSTANTE
)
# Nome proprio = capitalizada que NAO abre a frase. Em portugues isso e sinal forte.
_TOKEN = re.compile(r"\b[\wÀ-ÿ][\wÀ-ÿ-]*\b")


_CERCA = re.compile(r"```[a-zA-Z]*\n?")
# Marcadores de markdown nao contam como inicio de frase — senao o titulo de uma
# secao vira "nome proprio" e o alarme dispara em cabecalho.
_MARCADOR = re.compile(r"^\s*(?:#{1,6}|[-*+]|\d+[.)]|\([a-z0-9]+\))\s*", re.IGNORECASE)


def termos_especificos(texto: str) -> set[str]:
    """Numeros, identificadores, siglas e nomes proprios — o que da para conferir."""
    texto = _CERCA.sub("", texto)
    achados: set[str] = set()
    for m in _NUMERO.finditer(texto):
        achados.add(m.group(0).replace(" ", "").rstrip("."))
    for m in _CODIGO.finditer(texto):
        t = (m.group(1) or m.group(0)).strip()
        # Crase impar (a divisao em frases corta um trecho ao meio) faz o casamento
        # varrer prosa. Codigo inline com mais de 60 chars e artefato, nao identificador.
        if t and len(t) <= 60:
            achados.add(t)
    for f in _frases_cruas(texto):
        f = _MARCADOR.sub("", f)
        while _MARCADOR.match(f):          # "## (b) " tem dois marcadores
            f = _MARCADOR.sub("", f)
        tokens = list(_TOKEN.finditer(f))
        for i, m in enumerate(tokens):
            t = m.group(0)
            if i == 0 or not t[:1].isupper() or t.isupper():
                continue  # abre a frase, ou nao e capitalizada, ou ja virou sigla
            if len(t) >= 3 and normalizar(t) not in _VAZIAS:
                achados.add(t)
    return {t for t in achados if t.strip()}


def _frases_cruas(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.!?:])\s+|\n+", texto)
    return [p.strip() for p in partes if p.strip()]


def frases(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.!?:])\s+(?=[A-ZÀ-Ý])|\n{2,}", texto)
    return [p.strip() for p in partes if p.strip()]


@dataclass
class Acrescimo:
    frase: str
    termos: list[str]


@dataclass
class Auditoria:
    acrescimos: list[Acrescimo] = field(default_factory=list)
    frases_totais: int = 0
    termos_sintese: int = 0
    membros: list[str] = field(default_factory=list)
    erro: str = ""

    @property
    def limpo(self) -> bool:
        return not self.acrescimos and not self.erro


def auditar(rec: dict[str, Any]) -> Auditoria:
    """Varredura offline: o que a sintese afirma que nenhuma resposta continha."""
    sintese = (rec.get("synthesis") or {}).get("content") or ""
    respostas = [s.get("content") or "" for s in rec.get("stage1", []) if s.get("ok")]
    membros = [s["name"] for s in rec.get("stage1", []) if s.get("ok")]

    if not sintese:
        return Auditoria(erro="registro sem sintese", membros=membros)
    if not respostas:
        return Auditoria(erro="registro sem respostas para comparar", membros=membros)

    # Tudo que o conselho disse, normalizado, mais a propria pergunta: termo que
    # veio do enunciado nao e acrescimo do presidente.
    corpus = normalizar(" \n ".join(respostas) + " \n " + (rec.get("question") or ""))

    aud = Auditoria(membros=membros)
    todos = termos_especificos(sintese)
    aud.termos_sintese = len(todos)

    for f in frases(sintese):
        aud.frases_totais += 1
        ausentes = sorted(
            {t for t in termos_especificos(f) if normalizar(t) not in corpus},
            key=str.lower,
        )
        if ausentes:
            aud.acrescimos.append(Acrescimo(frase=f, termos=ausentes))
    return aud


def prompt_verificacao(rec: dict, aud: Auditoria) -> str:
    """Uma unica chamada, cega: o verificador nao sabe que julga um 'presidente'."""
    respostas = [s.get("content") or "" for s in rec.get("stage1", []) if s.get("ok")]
    fontes = "\n\n".join(f"### Fonte {chr(65 + i)}\n{t}" for i, t in enumerate(respostas))
    itens = "\n".join(f"{i + 1}. {a.frase}" for i, a in enumerate(aud.acrescimos))
    return f"""Voce confere se afirmacoes estao sustentadas por um conjunto de fontes.

FONTES:

{fontes}

AFIRMACOES A CONFERIR:
{itens}

Para cada afirmacao, decida se ela e SUSTENTADA pelas fontes — inclusive por parafrase
ou inferencia direta — ou se e ACRESCIMO, isto e, afirma algo que nenhuma fonte sustenta.
Na duvida, marque ACRESCIMO: o custo de deixar passar um acrescimo e maior que o de
sinalizar demais.

Responda EXATAMENTE neste formato, uma linha por afirmacao, sem mais nada depois:

VEREDITOS:
1 | SUSTENTADA ou ACRESCIMO | motivo em uma linha
2 | SUSTENTADA ou ACRESCIMO | motivo em uma linha"""


_LINHA = re.compile(r"^\s*(\d+)\s*\|\s*(SUSTENTADA|ACRESCIMO)\s*\|\s*(.*?)\s*$",
                    re.IGNORECASE | re.MULTILINE)


def parse_verificacao(texto: str, n: int) -> dict[int, tuple[str, str]]:
    fora = {}
    corte = texto.upper().rfind("VEREDITOS:")
    alvo = texto[corte + 10:] if corte >= 0 else texto
    for m in _LINHA.finditer(alvo):
        i = int(m.group(1))
        if 1 <= i <= n:
            fora[i] = (m.group(2).upper(), m.group(3)[:200])
    return fora
