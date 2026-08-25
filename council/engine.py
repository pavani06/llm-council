"""Orquestracao dos 3 estagios do conselho."""

from __future__ import annotations

import hashlib
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from .config import Config, Member
from .prompts import DEFAULT_CRITERIA, chairman_prompt, ranking_prompt, stage1_user_prompt
from .provenance import seal
from .providers import Reply
from .structured import parse_questions
from .ranking import (
    Ballot,
    assign_blind_labels,
    borda,
    divided,
    identity_terms,
    parse_ballot,
    scrub_identity,
)

Progress = Callable[[str, str], None]  # (estagio, mensagem)


def _noop(stage: str, msg: str) -> None:  # pragma: no cover
    pass


@dataclass
class Deliberation:
    """Entrada de uma execucao. Sem perfil e sem bundle e a pergunta pura de
    sempre; com perfil, ganha papeis por conselheiro e bundle de evidencia."""

    question: str
    profile: Any = None            # config.Profile | None
    bundle: str | None = None
    run_refs: list[str] = field(default_factory=list)


@dataclass
class Candidate:
    """Item ranqueavel no estagio 2. No caminho sem perfil, id = author = nome
    do membro (shape do registro identico ao historico); com questions, cada
    questao destilada e um candidato proprio."""

    id: str
    text: str
    author: str


def _distill(blind_answers: dict[str, str], stage1_format: str,
             member_index: dict[str, int]) -> tuple[list[Candidate], list[str]]:
    """Respostas ja cegas -> candidatos. questions destila cada questao; parse
    falho vira aviso nomeado, nao silencio."""
    avisos: list[str] = []
    out: list[Candidate] = []
    for name, txt in blind_answers.items():
        if stage1_format != "questions":
            out.append(Candidate(id=name, text=txt, author=name))
            continue
        questoes, erro = parse_questions(txt, 5)
        if erro:
            avisos.append(f"destilacao: {name}: {erro}")
            continue
        for q in questoes:
            texto = f"{q['pergunta']}\nRecomendacao: {q['recomendacao']}"
            out.append(Candidate(id=f"q{member_index[name]}-{q['id']}", text=texto, author=name))
    return out, avisos


@dataclass
class MemberAnswer:
    name: str
    provider: str
    model: str
    reply: Reply

    @property
    def ok(self) -> bool:
        return self.reply.ok


@dataclass
class Run:
    question: str
    seed: int
    started_at: str
    config_source: str
    producer: dict[str, Any] = field(default_factory=dict)
    members: list[dict[str, Any]] = field(default_factory=list)
    stage1: list[dict[str, Any]] = field(default_factory=list)
    stage2: list[dict[str, Any]] = field(default_factory=list)
    consensus: list[dict[str, Any]] = field(default_factory=list)
    synthesis: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    elapsed_s: float = 0.0
    divided: bool = False

    def digest(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(blob).hexdigest()


class Council:
    def __init__(self, cfg: Config, progress: Progress | None = None):
        self.cfg = cfg
        self.progress = progress or _noop

    # ------------------------------------------------------------- estagio 1

    def _ask_one(self, m: Member, spec: Deliberation) -> MemberAnswer:
        s = self.cfg.settings
        ep = self.cfg.endpoint(m.provider)
        if spec.profile is None:
            # caminho sem perfil: payload identico ao historico, uma mensagem user.
            messages = [{"role": "user", "content": spec.question}]
        else:
            user = stage1_user_prompt(
                spec.question, spec.bundle, spec.profile.stage1_format
            )
            papel = spec.profile.roles.get(m.name)
            if papel:
                messages = [
                    {"role": "system", "content": papel},
                    {"role": "user", "content": user},
                ]
            else:
                messages = [{"role": "user", "content": user}]
        reply = ep.chat(
            m.model,
            messages,
            temperature=s.temperature,
            max_tokens=s.max_tokens,
            timeout=s.timeout,
            retries=s.retries,
            params=m.params,
        )
        self.progress(
            "stage1",
            f"{m.name}: {'ok' if reply.ok else 'FALHOU — ' + reply.error}"
            + (f" ({reply.latency_s:.1f}s, {reply.usage.total} tok)" if reply.ok else ""),
        )
        return MemberAnswer(m.name, m.provider, m.model, reply)

    def stage1(self, spec: Deliberation, members: list[Member]) -> list[MemberAnswer]:
        self.progress("stage1", f"consultando {len(members)} conselheiros em paralelo")
        with ThreadPoolExecutor(max_workers=max(1, len(members))) as pool:
            return list(pool.map(lambda m: self._ask_one(m, spec), members))

    # ------------------------------------------------------------- estagio 2

    def _rank_one(
        self,
        ranker: Member,
        index: int,
        question: str,
        candidates: list[Candidate],
        seed: int,
        criteria=DEFAULT_CRITERIA,
    ) -> Ballot:
        s = self.cfg.settings
        elegiveis = [c for c in candidates
                     if not (s.exclude_self_rank and c.author == ranker.name)]
        if not elegiveis:
            # avaliador sem nada a julgar (todos os candidatos sao dele): cedula
            # invalida com motivo nomeado, nao prompt vazio nem silencio.
            ballot = Ballot(ranker=ranker.name, label_to_member={}, raw="",
                            ok=False, error="sem candidatos a avaliar apos auto-exclusao")
            self.progress("stage2", f"{ranker.name}: {ballot.error}")
            return ballot
        mapping = assign_blind_labels(
            [c.id for c in elegiveis], seed=seed, ranker_index=index, shuffle=s.shuffle_labels
        )
        por_rotulo = {}
        for lbl, cid in mapping.items():
            por_rotulo[lbl] = next(c.text for c in elegiveis if c.id == cid)
        prompt = ranking_prompt(question, por_rotulo, criteria=criteria)
        ep = self.cfg.endpoint(ranker.provider)
        reply = ep.chat(
            ranker.model,
            [{"role": "user", "content": prompt}],
            temperature=s.temperature,
            max_tokens=s.max_tokens,
            timeout=s.timeout,
            retries=s.retries,
            params=ranker.params,
        )
        ballot = Ballot(ranker=ranker.name, label_to_member=mapping, raw=reply.content,
                        truncated=reply.truncated)
        if not reply.ok:
            ballot.ok = False
            ballot.error = reply.error
            self.progress("stage2", f"{ranker.name}: FALHOU — {reply.error}")
            return ballot
        order, verdicts, err = parse_ballot(reply.content, list(mapping))
        ballot.order = order
        ballot.verdicts = verdicts
        ballot.error = err
        ballot.ok = bool(order)
        shown = " > ".join(mapping[l] for l in order if l in mapping) or "?"
        self.progress("stage2", f"{ranker.name}: {shown}" + (f"  [{err}]" if err else ""))
        return ballot

    def stage2(
        self, question: str, candidates: list[Candidate], members: list[Member], seed: int,
        criteria=DEFAULT_CRITERIA, answerers: set[str] | None = None,
    ) -> list[Ballot]:
        # avaliadores = quem respondeu no estagio 1; autor de candidato e papel
        # no ranking, nao requisito para avaliar (desacoplamento de papeis).
        if answerers is None:
            answerers = {c.author for c in candidates}
        rankers = [m for m in members if m.name in answerers]
        self.progress("stage2", f"{len(rankers)} avaliadores, cegos e sem auto-avaliacao")
        with ThreadPoolExecutor(max_workers=max(1, len(rankers))) as pool:
            return list(
                pool.map(
                    lambda pair: self._rank_one(pair[1], pair[0], question, candidates,
                                                seed, criteria),
                    enumerate(rankers),
                )
            )

    # ------------------------------------------------------------- estagio 3

    def stage3_stream(
        self, question: str, answers: dict[str, str], consensus, blind: bool
    ) -> Iterator[str]:
        s = self.cfg.settings
        chair = self.cfg.chairman
        prompt = chairman_prompt(question, answers, consensus, blind=blind)
        ep = self.cfg.endpoint(chair.provider)
        yield from ep.stream(
            chair.model,
            [{"role": "user", "content": prompt}],
            temperature=s.temperature,
            max_tokens=s.chairman_max_tokens,
            timeout=s.timeout,
            params=chair.params,
        )

    def stage3(self, question: str, answers: dict[str, str], consensus, blind: bool) -> Reply:
        s = self.cfg.settings
        chair = self.cfg.chairman
        prompt = chairman_prompt(question, answers, consensus, blind=blind)
        ep = self.cfg.endpoint(chair.provider)
        return ep.chat(
            chair.model,
            [{"role": "user", "content": prompt}],
            temperature=s.temperature,
            max_tokens=s.chairman_max_tokens,
            timeout=s.timeout,
            retries=s.retries,
            params=chair.params,
        )

    # ------------------------------------------------------------- run

    def run(self, question: str | Deliberation, *, skip_ranking: bool = False) -> Run:
        spec = question if isinstance(question, Deliberation) else Deliberation(question)
        question = spec.question  # corpo existente segue lendo 'question'
        s = self.cfg.settings
        seed = s.seed or random.SystemRandom().randrange(1, 2**31)
        t0 = time.monotonic()
        rec = Run(
            question=spec.question,
            seed=seed,
            started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            config_source=str(self.cfg.source),
        )
        # Sela o produtor ANTES de rodar: o registro tem de dizer qual codigo e qual
        # config o geraram, senao ele fica ininterpretavel apos qualquer edicao.
        from . import __version__
        rec.producer = seal(self.cfg, __version__)
        if rec.producer.get("git_dirty"):
            rec.warnings.append(
                "arvore de trabalho suja na execucao: o commit registrado nao endereca "
                "por inteiro o codigo que rodou (o code_sha256 endereca)"
            )

        members = self.cfg.active_members()
        skipped = [m for m in self.cfg.members if m not in members]
        for m in skipped:
            rec.warnings.append(
                f"{m.name} fora do conselho: {self.cfg.key_env_for(m.provider)} nao definida"
            )
        if not members:
            rec.warnings.append("nenhum conselheiro com chave configurada")
            rec.elapsed_s = time.monotonic() - t0
            return rec
        rec.members = [{"name": m.name, "provider": m.provider, "model": m.model} for m in members]

        # estagio 1
        answers_all = self.stage1(spec, members)
        rec.stage1 = [
            {"name": a.name, "provider": a.provider, "model": a.model, **a.reply.as_dict()}
            for a in answers_all
        ]
        answers = {a.name: a.reply.content for a in answers_all if a.ok}
        for a in answers_all:
            if not a.ok:
                rec.warnings.append(f"estagio 1: {a.name} falhou — {a.reply.error}")
            elif a.reply.truncated:
                rec.warnings.append(
                    f"estagio 1: resposta de {a.name} truncada por max_tokens — aumente o teto dele em [params]"
                )

        # Cegamento real: mascara autoidentificacao antes de qualquer julgamento.
        blind_answers = dict(answers)
        if s.scrub_identity and answers:
            terms = identity_terms(members, s.identity_terms)
            for name, txt in answers.items():
                cleaned, hits = scrub_identity(txt, terms, question)
                blind_answers[name] = cleaned
                if hits:
                    for entry in rec.stage1:
                        if entry["name"] == name:
                            entry["masked_terms"] = hits
        if not answers:
            rec.warnings.append("nenhuma resposta no estagio 1; nada a sintetizar")
            rec.elapsed_s = time.monotonic() - t0
            return rec

        # Destilacao: respostas cegas viram candidatos (questions: uma questao =
        # um candidato; demais formatos: uma resposta = um candidato).
        fmt = spec.profile.stage1_format if spec.profile else "prose"
        member_index = {m.name: i for i, m in enumerate(members)}
        candidates, avisos_destilacao = _distill(blind_answers, fmt, member_index)
        rec.warnings.extend(avisos_destilacao)

        # estagio 2
        consensus = []
        if not skip_ranking and len(candidates) >= 3:
            criteria = (spec.profile.criteria if spec.profile and spec.profile.criteria
                        else DEFAULT_CRITERIA)
            ballots = self.stage2(question, candidates, members, seed, criteria,
                                  answerers=set(answers))
            rec.stage2 = [
                {
                    "ranker": b.ranker,
                    "ok": b.ok,
                    "error": b.error,
                    "label_to_member": b.label_to_member,
                    "order_labels": b.order,
                    "order_members": b.ranked_members,
                    "verdicts": {k: list(v) for k, v in b.verdicts.items()},
                    "raw": b.raw,
                }
                for b in ballots
            ]
            for b in ballots:
                if not b.ok:
                    extra = " (resposta truncada por max_tokens)" if b.truncated else ""
                    rec.warnings.append(f"estagio 2: cedula de {b.ranker} descartada — {b.error}{extra}")
                elif b.truncated:
                    rec.warnings.append(f"estagio 2: cedula de {b.ranker} veio truncada por max_tokens")
            consensus = borda(ballots, [c.id for c in candidates])
            rec.consensus = [asdict(c) for c in consensus]
            rec.divided = divided(consensus)
            if rec.divided:
                rec.warnings.append(
                    "conselho dividido: topo sem folga clara — trate a sintese como uma opcao, nao consenso"
                )
        elif not skip_ranking:
            rec.warnings.append(
                f"estagio 2 pulado: com auto-exclusao sao necessarios 3+ candidatos (havia {len(candidates)})"
            )

        # estagio 3
        self.progress("stage3", f"presidente {self.cfg.chairman.label} sintetizando")
        reply = self.stage3(
            question,
            blind_answers if s.blind_chairman else answers,
            consensus,
            blind=s.blind_chairman,
        )
        rec.synthesis = {
            "name": self.cfg.chairman.name,
            "provider": self.cfg.chairman.provider,
            "model": self.cfg.chairman.model,
            "blind": s.blind_chairman,
            **reply.as_dict(),
        }
        if not reply.ok:
            rec.warnings.append(f"estagio 3: presidente falhou — {reply.error}")

        rec.usage = _total_usage(rec)
        rec.elapsed_s = round(time.monotonic() - t0, 2)
        return rec


def _total_usage(rec: Run) -> dict[str, int]:
    tot = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    blocks = list(rec.stage1) + ([rec.synthesis] if rec.synthesis else [])
    for b in blocks:
        u = b.get("usage") or {}
        for k in tot:
            tot[k] += int(u.get(k) or 0)
    return tot


def save_run(rec: Run, runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    digest = rec.digest()
    stamp = rec.started_at.replace(":", "").replace("-", "")
    path = runs_dir / f"{stamp}-{digest[:12]}.json"
    payload = asdict(rec) | {"sha256": digest}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
