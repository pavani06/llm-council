"""Cegamento, parsing de cedulas e agregacao Borda."""

from __future__ import annotations

import random
import re
import statistics
from dataclasses import dataclass, field


def labels_for(n: int) -> list[str]:
    return [chr(65 + i) for i in range(n)]


@dataclass
class Ballot:
    """Cedula de um avaliador: rotulos cegos -> nomes reais, mais a ordem que ele produziu."""

    ranker: str
    label_to_member: dict[str, str]
    order: list[str] = field(default_factory=list)          # rotulos, do melhor ao pior
    verdicts: dict[str, tuple[str, str]] = field(default_factory=dict)  # rotulo -> (forte, fraco)
    ok: bool = True
    error: str = ""
    raw: str = ""
    truncated: bool = False

    @property
    def ranked_members(self) -> list[str]:
        return [self.label_to_member[l] for l in self.order if l in self.label_to_member]


def assign_blind_labels(
    candidates: list[str], *, seed: int, ranker_index: int, shuffle: bool
) -> dict[str, str]:
    """Rotulos cegos por avaliador. Embaralhar mata o vies de posicao (todos veem ordem diferente)."""
    ordered = list(candidates)
    if shuffle:
        rng = random.Random((seed << 8) ^ (ranker_index + 1))
        rng.shuffle(ordered)
    return dict(zip(labels_for(len(ordered)), ordered))


# Modelo real nao obedece formato ao pe da letra: escreve "1. **Resposta A**", traduz o
# cabecalho, poe negrito. O parser aceita essas variantes, mas continua se recusando a
# adivinhar ordem quando nao ha ranking algum.
_LABEL_WORD = r"(?:respostas?|response|op[cç][ãa]o|option|alternativa)"
_RANK_LINE = re.compile(
    r"^\s*(\d+)\s*[.)\-]\s*[*_`\"']*\s*(?:" + _LABEL_WORD + r")?\s*[:\-]?\s*[*_`\"']*\s*([A-Za-z])(?![\w])",
    re.IGNORECASE | re.MULTILINE,
)
_VERDICT_LINE = re.compile(
    r"^\s*[*_`]*\s*(?:" + _LABEL_WORD + r")?\s*([A-Za-z])\s*[*_`]*\s*\|\s*(.*?)\s*\|\s*(.*?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_RANK_HEADERS = ("FINAL RANKING", "RANKING FINAL", "CLASSIFICACAO FINAL", "CLASSIFICAÇÃO FINAL",
                 "ORDENACAO FINAL", "ORDENAÇÃO FINAL", "RANQUEAMENTO FINAL")
_VERDICT_HEADERS = ("VERDICTS", "VEREDICTOS", "VEREDITOS", "VEREDITO", "AVALIACOES", "AVALIAÇÕES")


def parse_ballot(text: str, valid_labels: list[str]) -> tuple[list[str], dict[str, tuple[str, str]], str]:
    """Extrai (ordem, veredictos, erro). Tolerante a desvio de formato, mas nunca inventa ordem."""
    valid = set(valid_labels)

    verdicts: dict[str, tuple[str, str]] = {}
    vsec = _section(text, _VERDICT_HEADERS)
    for m in _VERDICT_LINE.finditer(vsec or ""):
        lbl = m.group(1).upper()
        if lbl in valid:
            verdicts[lbl] = (m.group(2)[:280], m.group(3)[:280])

    rsec = _section(text, _RANK_HEADERS)
    order: list[str] = []
    seen: set[str] = set()
    for m in _RANK_LINE.finditer(rsec if rsec is not None else text):
        lbl = m.group(2).upper()
        if lbl in valid and lbl not in seen:
            seen.add(lbl)
            order.append(lbl)

    if not order:
        return [], verdicts, "nenhuma linha de ranking reconhecida"
    missing = valid - seen
    if missing:
        # cedula parcial: aceita, mas registra. Faltantes ficam empatados no fim.
        order = order + sorted(missing)
        return order, verdicts, f"cedula parcial, faltavam {sorted(missing)} (colocados no fim)"
    return order, verdicts, ""


def _section(text: str, headers: tuple[str, ...]) -> str | None:
    """Trecho apos o ultimo cabecalho reconhecido, em qualquer das variantes aceitas."""
    up = text.upper()
    best = -1
    end = 0
    for h in headers:
        idx = up.rfind(h)
        if idx > best:
            best, end = idx, idx + len(h)
    if best < 0:
        return None
    return text[end:]


@dataclass
class Consensus:
    member: str
    score: float          # 0..1, media normalizada de Borda
    positions: list[int]  # posicao (1-based) em cada cedula onde apareceu
    ballots: int
    spread: float         # desvio-padrao das posicoes; alto = conselho dividido
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)


def borda(ballots: list[Ballot], members: list[str]) -> list[Consensus]:
    """Borda normalizado. Com auto-exclusao toda resposta aparece em N-1 cedulas do mesmo tamanho,
    entao a comparacao e balanceada."""
    points: dict[str, list[float]] = {m: [] for m in members}
    positions: dict[str, list[int]] = {m: [] for m in members}
    pros: dict[str, list[str]] = {m: [] for m in members}
    cons: dict[str, list[str]] = {m: [] for m in members}

    for b in ballots:
        if not b.ok or not b.order:
            continue
        k = len(b.order)
        if k < 2:
            continue
        for pos, lbl in enumerate(b.order, start=1):
            member = b.label_to_member.get(lbl)
            if member is None or member not in points:
                continue
            points[member].append((k - pos) / (k - 1))
            positions[member].append(pos)
            v = b.verdicts.get(lbl)
            if v:
                if v[0]:
                    pros[member].append(v[0])
                if v[1]:
                    cons[member].append(v[1])

    out = []
    for m in members:
        pts = points[m]
        pos = positions[m]
        out.append(
            Consensus(
                member=m,
                score=round(sum(pts) / len(pts), 4) if pts else 0.0,
                positions=pos,
                ballots=len(pts),
                spread=round(statistics.pstdev(pos), 3) if len(pos) > 1 else 0.0,
                strengths=pros[m],
                weaknesses=cons[m],
            )
        )
    out.sort(key=lambda c: (-c.score, c.spread, c.member))
    return out


def divided(consensus: list[Consensus]) -> bool:
    """Conselho dividido: topo e vice praticamente empatados, ou alta dispersao no topo."""
    scored = [c for c in consensus if c.ballots]
    if len(scored) < 2:
        return False
    return (scored[0].score - scored[1].score) < 0.15 or scored[0].spread >= 1.0


# --------------------------------------------------------------------- scrub

# Marcas que um modelo costuma deixar na propria resposta ("como o ChatGPT...",
# "sou um modelo da DeepSeek"). Se elas passarem, o cegamento do estagio 2 e ficticio.
DEFAULT_IDENTITY_TERMS = (
    "chatgpt", "openai", "gpt-5", "gpt-4", "gpt", "o3-mini", "codex",
    "deepseek", "glm", "zhipu", "z.ai", "zai",
    "claude", "anthropic", "gemini", "google deepmind", "bard",
    "qwen", "alibaba", "llama", "meta ai", "mistral", "grok", "xai", "kimi", "moonshot",
)

_MASK = "[modelo]"


def identity_terms(members, extra=()) -> list[str]:
    terms = set(DEFAULT_IDENTITY_TERMS)
    for m in members:
        terms.add(m.name.lower())
        terms.add(m.provider.lower())
        for tok in re.split(r"[-/._]", m.model.lower()):
            if len(tok) >= 3 and not tok.isdigit():
                terms.add(tok)
    terms.update(t.lower() for t in extra)
    # termos mais longos primeiro para "z.ai" nao virar "z" + ".ai"
    return sorted(terms, key=len, reverse=True)


def scrub_identity(text: str, terms: list[str], question: str) -> tuple[str, list[str]]:
    """Mascara autoidentificacao antes do ranqueamento cego.

    Um termo citado na propria pergunta NAO e mascarado — se o operador perguntou sobre
    GPT, apagar 'GPT' das respostas destruiria o conteudo. Cegar nunca pode custar o assunto.
    """
    q = question.lower()
    hit = []
    out = text
    for term in terms:
        if term in q:
            continue
        pattern = re.compile(r"(?<![\w.])" + re.escape(term) + r"(?![\w])", re.IGNORECASE)
        out, n = pattern.subn(_MASK, out)
        if n:
            hit.append(term)
    return out, hit
