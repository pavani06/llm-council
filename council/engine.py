"""Orquestracao dos 3 estagios do conselho."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from .config import Config, Member
from .prompts import (DEFAULT_CRITERIA, chairman_prompt, linhagem_section,
                      ranking_prompt, stage1_user_prompt)
from .provenance import config_digest, seal
from .providers import Reply
from .runs import partial_path, stamp_for
from .structured import parse_decision, parse_proposal, parse_questions
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
    # preenchido pelo engine a partir de run_refs; nao vem do chamador
    linhagem: str | None = None


@dataclass
class Candidate:
    """Item ranqueavel no estagio 2. No caminho sem perfil, id = author = nome
    do membro (shape do registro identico ao historico); com questions, cada
    questao destilada e um candidato proprio; com proposal, o candidato e a
    proposta destilada (titulo + corpo), uma por membro — id segue o membro."""

    id: str
    text: str
    author: str


def _distill(blind_answers: dict[str, str], stage1_format: str,
             member_index: dict[str, int]) -> tuple[list[Candidate], list[str]]:
    """Respostas ja cegas -> candidatos. questions destila cada questao;
    proposal destila a proposta (titulo + corpo); parse falho vira aviso
    nomeado, nao silencio."""
    avisos: list[str] = []
    out: list[Candidate] = []
    for name, txt in blind_answers.items():
        if stage1_format == "proposal":
            proposta, erro = parse_proposal(txt)
            if erro:
                avisos.append(f"destilacao: {name}: {erro}")
                continue
            out.append(Candidate(id=name,
                                 text=f"{proposta['titulo']}\n\n{proposta['corpo']}",
                                 author=name))
            continue
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
    # deliberacao (aditivo, defaults neutros: registro antigo le igual)
    profile_name: str | None = None
    bundle_sha256: str | None = None
    run_refs: list[str] = field(default_factory=list)
    run_refs_sha256: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    decision: dict[str, Any] | None = None
    # sobrevivencia (aditivo, defaults neutros: so parcial nasce marcado)
    partial: bool = False
    stage_reached: str = ""
    interrupted: bool = False
    interruption_reason: str | None = None
    # custo por estagio (aditivo, {} = registro anterior a C2; 'usage' segue
    # com o significado historico dele, estagio 1 + presidente)
    usage_by_stage: dict[str, dict[str, int]] = field(default_factory=dict)
    # rotulo cego -> id real (aditivo, {} sem decider cego): resolve o
    # "Candidato B" do texto do presidente sem reconstruir a ordem do consenso
    decision_aliases: dict[str, str] = field(default_factory=dict)
    # retomada de parcial (aditivo, Emenda 2: None ou ausente = execucao
    # integral; presente = sha256 do parcial que originou este registro)
    resumed_from: str | None = None
    # estagio 2 (aditivo, Emenda 2: "full" | "lite"; registro antigo sem o
    # campo le como "full" — deliberação plena, leitura retroativa)
    stage2_mode: str = "full"

    def digest(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(blob).hexdigest()


@dataclass
class Interruption:
    """Sinal recebido, lido no proximo limite de estagio.

    Threads de chamada nao sao interrompiveis no meio: a granularidade honesta
    e o limite de estagio. O handler so marca aqui; quem grava e decide parar e
    o engine.
    """

    requested: bool = False
    reason: str = ""

    def request(self, reason: str) -> None:
        self.requested = True
        self.reason = reason


class RunInterrupted(Exception):
    """Execucao parada num limite de estagio por sinal.

    O parcial ficou em disco com o que ja foi pago; o registro final NAO foi
    gravado — execucao interrompida nao entra em denominador como se tivesse
    terminado.
    """

    def __init__(self, rec: Run, path: Path, stage: str, reason: str):
        super().__init__(f"{reason} — parou em '{stage}', parcial em {path.name}")
        self.rec = rec
        self.path = path
        self.stage = stage
        self.reason = reason


class ResumeError(Exception):
    """Guarda de retomada falhou: fail-closed, erro nomeado, nada gravado.

    O codigo (partial_not_found, not_partial, stage2_incomplete, stage2_lite,
    config_drift, resume_invalid_args) e a interface: o CLI imprime o codigo e sai
    nao-zero sem escrever arquivo algum.
    """

    def __init__(self, code: str, msg: str):
        super().__init__(f"{code}: {msg}")
        self.code = code


class RefError(Exception):
    """Referencia de linhagem inutilizavel: fail-closed, erro nomeado.

    O codigo (ref_not_found, ref_sem_sintese) e a interface, como no ResumeError.
    """

    def __init__(self, code: str, msg: str):
        super().__init__(f"{code}: {msg}")
        self.code = code


def linhagem_de_refs(refs: list[str], runs_dir: Path | None) -> str | None:
    """Le os registros referidos e monta a secao de linhagem. UM NIVEL.

    Nao segue o `run_refs` do referido: puxar transitivamente faria o custo
    explodir e o conteudo degradar a cada salto.

    Referencia degenerada REPROVA em vez de injetar o que houver. Injetar uma
    sintese que falhou alimentaria o conselho com um nao-resultado como se fosse
    conclusao, e o registro novo selaria linhagem para uma deliberacao que nao
    concluiu — que e a classe de defeito que este conserto remove, um nivel
    acima. Parcial e interrompido nao chegam aqui: o CLI e o MCP resolvem os
    prefixos por `final_runs()`, que ja os exclui.
    """
    if not refs:
        return None
    if runs_dir is None:
        raise RefError("ref_not_found", "run_refs pedido sem runs_dir para resolver")
    carregados: list[dict[str, Any]] = []
    for sha in refs:
        achado = None
        for p in sorted(Path(runs_dir).glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(d, dict) and d.get("sha256") == sha:
                achado = d
                break
        if achado is None:
            raise RefError("ref_not_found",
                           f"registro {sha[:12]} nao encontrado em {runs_dir}")
        syn = achado.get("synthesis") or {}
        if not syn.get("ok") or not str(syn.get("content") or "").strip():
            raise RefError("ref_sem_sintese",
                           f"registro {sha[:12]} nao tem sintese utilizavel "
                           f"(ok={syn.get('ok')!r}) — referir uma deliberacao que nao "
                           f"concluiu injetaria nao-resultado como conclusao")
        carregados.append(achado)
    return linhagem_section(carregados)


class Council:
    def __init__(self, cfg: Config, progress: Progress | None = None):
        self.cfg = cfg
        self.progress = progress or _noop

    # ------------------------------------------------------------- estagio 1

    def _ask_one(self, m: Member, spec: Deliberation) -> MemberAnswer:
        s = self.cfg.settings
        ep = self.cfg.endpoint(m.provider)
        if spec.profile is None and not spec.linhagem:
            # caminho sem perfil: payload identico ao historico, uma mensagem user.
            messages = [{"role": "user", "content": spec.question}]
        else:
            # com linhagem e sem perfil, o formato e prose: o que muda e a secao
            # nova, nao a diretiva. Sem linhagem, este ramo e o de sempre.
            user = stage1_user_prompt(
                spec.question, spec.bundle,
                spec.profile.stage1_format if spec.profile else "prose",
                linhagem=spec.linhagem,
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
        if len(elegiveis) < 2:
            # um unico candidato nao e ranking comparavel; o Borda descartaria
            # a cedula em silencio — aqui ela nasce invalida com motivo.
            ballot = Ballot(ranker=ranker.name, label_to_member={}, raw="",
                            ok=False,
                            error=f"apenas {len(elegiveis)} candidato elegivel apos auto-exclusao (minimo 2)")
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
                        truncated=reply.truncated, usage=reply.usage.as_dict(),
                        latency_s=round(reply.latency_s, 2))
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
        self.progress("stage2", f"{ranker.name}: {shown}"
                      + f" ({reply.latency_s:.1f}s, {reply.usage.total} tok)"
                      + (f"  [{err}]" if err else ""))
        return ballot

    def stage2(
        self, question: str, candidates: list[Candidate], members: list[Member], seed: int,
        criteria=DEFAULT_CRITERIA, answerers: set[str] | None = None,
        lite: bool = False,
    ) -> list[Ballot]:
        # avaliadores = quem respondeu no estagio 1; autor de candidato e papel
        # no ranking, nao requisito para avaliar (desacoplamento de papeis).
        if answerers is None:
            answerers = {c.author for c in candidates}
        rankers = [m for m in members if m.name in answerers]
        if lite:
            # modo orcavel: primeiros max(2, metade) na ORDEM DA CONFIG —
            # deterministico, sem escolha por modelo
            rankers = rankers[:max(2, len(answerers) // 2)]
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
        self, question: str, answers: dict[str, str], consensus, blind: bool,
        mode: str = "synthesizer", divided: bool = False,
    ) -> Iterator[str]:
        s = self.cfg.settings
        chair = self.cfg.chairman
        prompt = chairman_prompt(question, answers, consensus, blind=blind,
                                  mode=mode, divided=divided)
        ep = self.cfg.endpoint(chair.provider)
        yield from ep.stream(
            chair.model,
            [{"role": "user", "content": prompt}],
            temperature=s.temperature,
            max_tokens=s.chairman_max_tokens,
            timeout=s.timeout,
            params=chair.params,
        )

    def stage3(
        self, question: str, answers: dict[str, str], consensus, blind: bool,
        mode: str = "synthesizer", divided: bool = False,
    ) -> Reply:
        s = self.cfg.settings
        chair = self.cfg.chairman
        prompt = chairman_prompt(question, answers, consensus, blind=blind,
                                  mode=mode, divided=divided)
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

    def _herdar_estagios(self, rec: Run, par: Run,
                         par_sha: str) -> tuple[dict[str, str], dict[str, str],
                                                list[Candidate], list]:
        """Retomada: estagios 1-2 do parcial entram verbatim no registro novo.

        O consenso NAO e copiado: e recomputado pela borda a partir dos ballots
        herdados — deterministico e sem rede, o mesmo resultado de sempre. O
        cegamento da sintese e reconstituido pela mesma funcao de scrub (a
        config e idêntica, garantida pelo guarda config_drift, logo os termos
        tambem sao — o resultado e o mesmo cegamento da execucao original).
        """
        rec.members = [dict(m) for m in par.members]
        rec.stage1 = [dict(e) for e in par.stage1]
        rec.stage2 = [dict(e) for e in par.stage2]
        # O modo do estagio 2 acompanha as cedulas que ele produziu. Sem isto o
        # retomado nasce com o default "full" e o registro afirmaria deliberacao
        # plena sobre cedulas de um estagio 2 reduzido — proveniencia falsa no
        # artefato selado. Registro antigo sem o campo le como "full" pelo
        # default do dataclass, que e o que ele de fato era.
        rec.stage2_mode = par.stage2_mode
        rec.candidates = [dict(c) for c in par.candidates]
        if par.decision is not None:
            rec.decision = dict(par.decision)
        answers = {e["name"]: e["content"] for e in rec.stage1 if e.get("ok")}
        blind_answers = dict(answers)
        s = self.cfg.settings
        if s.scrub_identity and answers:
            terms = identity_terms(self.cfg.active_members(), s.identity_terms)
            for name, txt in answers.items():
                blind_answers[name], _ = scrub_identity(txt, terms, rec.question)
        candidates = [Candidate(id=c["id"], text=c["text"], author=c["author"])
                      for c in par.candidates]
        ballots = [_ballot_do_registro(b) for b in par.stage2]
        consensus = borda(ballots, [c.id for c in candidates])
        rec.consensus = [asdict(c) for c in consensus]
        rec.divided = divided(consensus)
        rec.warnings.append(f"estágios 1-2 herdados de {par_sha[:12]}")
        return answers, blind_answers, candidates, consensus

    def _checkpoint(self, rec: Run, stage: str, runs_dir: Path | None,
                    interruption: Interruption | None, t0: float) -> None:
        """Limite de estagio: grava o parcial e, se um sinal chegou, para aqui."""
        if runs_dir is None:
            return
        parando = interruption is not None and interruption.requested
        if parando:
            rec.interrupted = True
            rec.interruption_reason = interruption.reason
        path = write_partial(rec, runs_dir, stage, time.monotonic() - t0)
        if parando:
            raise RunInterrupted(rec, path, stage, interruption.reason)

    def run(self, question: str | Deliberation | None = None, *, skip_ranking: bool = False,
            runs_dir: Path | None = None,
            interruption: Interruption | None = None,
            resume_from: tuple[Run, str] | None = None,
            rank_lite: bool = False) -> Run:
        if resume_from is None and not isinstance(question, (str, Deliberation)):
            raise ValueError("run(): passe a pergunta (str ou Deliberation) ou resume_from")
        s = self.cfg.settings
        t0 = time.monotonic()
        par: Run | None = None
        par_sha = ""
        if resume_from is not None:
            par, par_sha = resume_from
            spec = Deliberation(par.question)
            seed = par.seed  # herdado verbatim: o consenso recomputado depende dele
        else:
            spec = question if isinstance(question, Deliberation) else Deliberation(question)
            seed = s.seed or random.SystemRandom().randrange(1, 2**31)
        question = spec.question  # corpo existente segue lendo 'question'
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

        # deliberacao: campos da spec entram no registro ANTES de qualquer
        # retorno antecipado — falha sem membros nao pode apagar a origem
        if spec.profile is not None:
            rec.profile_name = spec.profile.name
        rec.run_refs = list(spec.run_refs)
        if spec.bundle is not None:
            rec.bundle_sha256 = hashlib.sha256(spec.bundle.encode("utf-8")).hexdigest()
        # A linhagem vira conteudo aqui e e SELADA, espelhando bundle_sha256: um
        # registro que afirma linhagem tem de endereçar o que de fato injetou,
        # senao o conserto reproduz o defeito que remove, um nivel acima.
        #
        # Depois dos campos da spec de proposito: linhagem_de_refs pode levantar,
        # e a invariante acima diz que a origem entra no registro ANTES de
        # qualquer retorno antecipado.
        spec.linhagem = linhagem_de_refs(spec.run_refs, runs_dir)
        if spec.linhagem is not None:
            rec.run_refs_sha256 = hashlib.sha256(spec.linhagem.encode("utf-8")).hexdigest()
        if resume_from is not None:
            # antes do 1o checkpoint: o rastro propio do resume ja nasce com o
            # sufixo -r e nunca colide com o parcial referenciado
            rec.resumed_from = par_sha
        self._checkpoint(rec, "seal", runs_dir, interruption, t0)

        # retomada: estagios 1-2 do parcial entram verbatim, consenso e
        # recomputado dos ballots herdados (borda deterministica, sem rede) e
        # o fluxo salta direto para o estagio 3, que e o bloco unico de sempre
        if resume_from is not None:
            answers, blind_answers, candidates, consensus = (
                self._herdar_estagios(rec, par, par_sha))
            self._checkpoint(rec, "stage2", runs_dir, interruption, t0)

        if resume_from is None:
            members = self.cfg.active_members()
            skipped = [m for m in self.cfg.members if m not in members]
            for m in skipped:
                rec.warnings.append(
                    f"{m.name} fora do conselho: {self.cfg.key_env_for(m.provider)} nao definida"
                )
            if not members:
                rec.warnings.append("nenhum conselheiro com chave configurada")
                rec.usage_by_stage = _usage_by_stage(rec)
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
            self._checkpoint(rec, "stage1", runs_dir, interruption, t0)

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
                # resposta que falhou pode ter custado (o modelo gasta o teto raciocinando
                # e devolve ok=False com usage) — o registro tem de dizer isso
                rec.usage_by_stage = _usage_by_stage(rec)
                rec.elapsed_s = time.monotonic() - t0
                return rec

            # Destilacao: respostas cegas viram candidatos (questions: uma questao =
            # um candidato; proposal: a proposta destilada de cada membro; demais:
            # uma resposta = um candidato).
            fmt = spec.profile.stage1_format if spec.profile else "prose"
            member_index = {m.name: i for i, m in enumerate(members)}
            candidates, avisos_destilacao = _distill(blind_answers, fmt, member_index)
            rec.warnings.extend(avisos_destilacao)
            rec.candidates = [{"id": c.id, "text": c.text, "author": c.author} for c in candidates]

            # estagio 2
            consensus = []
            if not skip_ranking and len(candidates) >= 3:
                criteria = (spec.profile.criteria if spec.profile and spec.profile.criteria
                            else DEFAULT_CRITERIA)
                ballots = self.stage2(question, candidates, members, seed, criteria,
                                      answerers=set(answers), lite=rank_lite)
                if rank_lite:
                    rec.stage2_mode = "lite"
                    rec.warnings.append(
                        f"estágio 2 em modo lite (deliberação não plena): "
                        f"{len(ballots)}/{len(set(answers))} avaliadores"
                    )
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
                        "usage": b.usage,
                        "latency_s": b.latency_s,
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
            self._checkpoint(rec, "stage2", runs_dir, interruption, t0)

        # estagio 3: synthesizer (padrao) ou decider (perfil), uma unica chamada
        mode = spec.profile.chairman_mode if spec.profile else "synthesizer"
        self.progress("stage3", f"presidente {self.cfg.chairman.label} "
                                f"{'decidindo' if mode == 'decider' else 'sintetizando'}")
        alias_decisao: dict[str, str] = {}
        if mode == "decider":
            if not candidates:
                # sem candidatos destilados nao ha o que decidir: nao se chama o
                # presidente, a falha entra nomeada no registro.
                rec.warnings.append(
                    "estagio 3: decisao impossivel — nenhum candidato destilado"
                )
                rec.usage = _total_usage(rec)
                rec.usage_by_stage = _usage_by_stage(rec)
                rec.elapsed_s = round(time.monotonic() - t0, 2)
                return rec
            if s.blind_chairman:
                # candidatos e tabela exibidos por rotulo cego; a decisao volta
                # traduzida para o id real antes de entrar no registro.
                ordenados = [c.member for c in consensus if c.ballots]
                ordenados += [c.id for c in candidates if c.id not in ordenados]
                for i, cid in enumerate(ordenados):
                    alias_decisao[cid] = f"Candidato {chr(65 + i)}"
                rec.decision_aliases = {v: k for k, v in alias_decisao.items()}
                mostrados = {alias_decisao[c.id]: c.text for c in candidates}
                cons_mostrado = [replace(c, member=alias_decisao.get(c.member, c.member))
                                 for c in consensus]
            else:
                mostrados = {c.id: c.text for c in candidates}
                cons_mostrado = consensus
            reply = self.stage3(question, mostrados, cons_mostrado,
                                blind=s.blind_chairman, mode="decider",
                                divided=rec.divided)
        else:
            reply = self.stage3(question, blind_answers if s.blind_chairman else answers,
                                consensus, blind=s.blind_chairman)
        rec.synthesis = {
            "name": self.cfg.chairman.name,
            "provider": self.cfg.chairman.provider,
            "model": self.cfg.chairman.model,
            "blind": s.blind_chairman,
            **reply.as_dict(),
        }
        if not reply.ok:
            rec.warnings.append(f"estagio 3: presidente falhou — {reply.error}")
        elif mode == "decider":
            dec, derr = parse_decision(reply.content, list(alias_decisao.values()) or
                                       [c.id for c in candidates])
            if derr:
                rec.warnings.append(f"estagio 3: decisao ilegivel — {derr}")
            else:
                if alias_decisao:
                    dec["escolha"] = {v: k for k, v in alias_decisao.items()}[dec["escolha"]]
                rec.decision = dec
        self._checkpoint(rec, "synthesis", runs_dir, interruption, t0)

        rec.usage = _total_usage(rec)
        rec.usage_by_stage = _usage_by_stage(rec)
        rec.elapsed_s = round(time.monotonic() - t0, 2)
        return rec


def _somar_usage(blocks: list[dict[str, Any]]) -> dict[str, int]:
    tot = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for b in blocks:
        u = b.get("usage") or {}
        for k in tot:
            tot[k] += int(u.get(k) or 0)
    return tot


def _total_usage(rec: Run) -> dict[str, int]:
    """Conta historica do campo 'usage': estagio 1 + presidente, sem o estagio 2.

    Nao se corrige — registro antigo tem de continuar significando o que
    significava. A verdade completa vive no 'usage_by_stage'.
    """
    return _somar_usage(list(rec.stage1) + ([rec.synthesis] if rec.synthesis else []))


def _usage_by_stage(rec: Run) -> dict[str, dict[str, int]]:
    """Custo decomposto, com o estagio 2 que o 'usage' nunca somou.

    'total' sai da MESMA funcao de soma dos tres estagios: a identidade
    aritmetica e estrutural, nao coincidencia de duas contas escritas a mao.
    """
    sintese = [rec.synthesis] if rec.synthesis else []
    return {
        "stage1": _somar_usage(list(rec.stage1)),
        "stage2": _somar_usage(list(rec.stage2)),
        "synthesis": _somar_usage(sintese),
        "total": _somar_usage(list(rec.stage1) + list(rec.stage2) + sintese),
    }


def _ballot_do_registro(b: dict[str, Any]) -> Ballot:
    """Reconstitui Ballot da entrada do registro (estagio 2 herdado)."""
    return Ballot(
        ranker=b.get("ranker", ""),
        label_to_member=b.get("label_to_member") or {},
        order=b.get("order_labels") or [],
        verdicts={k: (v[0], v[1]) for k, v in (b.get("verdicts") or {}).items()},
        ok=bool(b.get("ok")),
        error=b.get("error") or "",
        raw=b.get("raw") or "",
        truncated=bool(b.get("truncated")),
        usage=b.get("usage"),
        latency_s=b.get("latency_s"),
    )


def load_partial_for_resume(runs_dir: Path, sha_prefix: str, cfg: Config) -> tuple[Run, str]:
    """Localiza e valida o parcial para `council ask --resume <sha-parcial>`.

    Devolve (Run do parcial, sha256 integral). Guardas fail-closed, cada um com
    codigo nomeado e NENHUM arquivo gravado:
    - partial_not_found: prefixo sem match unico em runs/*.json
    - not_partial: o registro casado tem partial != true
    - stage2_incomplete: parcial parou antes do estagio 2 completo (todas as
      cedulas dos avaliadores elegiveis ok)
    - stage2_lite: o estagio 2 rodou em modo lite. Esta completo para o modo,
      mas deliberacao nao plena nao e retomavel (politica, nao incompletude)
    - config_drift: o config_sha256 selado no parcial difere da config atual
    """
    if not runs_dir.is_dir():
        raise ResumeError("partial_not_found", f"{runs_dir} nao existe")
    casos: list[tuple[Path, dict[str, Any], str]] = []
    ilegiveis = 0
    for p in sorted(runs_dir.glob("*.json")):
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            ilegiveis += 1
            continue
        if not isinstance(payload, dict):
            ilegiveis += 1
            continue
        sha = payload.get("sha256") or ""
        if isinstance(sha, str) and sha.startswith(sha_prefix):
            casos.append((p, payload, sha))
    if not casos:
        extra = f" ({ilegiveis} arquivo(s) ilegivel(e) ignorado(s))" if ilegiveis else ""
        raise ResumeError("partial_not_found",
                          f"nenhum registro casa o prefixo '{sha_prefix}' em {runs_dir}{extra}")
    if len(casos) > 1:
        raise ResumeError("partial_not_found",
                          f"prefixo '{sha_prefix}' ambiguo: {len(casos)} registros casam"
                          " — passe um prefixo maior")
    path, payload, sha = casos[0]
    if payload.get("partial") is not True:
        raise ResumeError("not_partial",
                          f"{path.name} e registro final, nao parcial — o resume retoma parcial")
    campos = {f.name for f in fields(Run)}
    rec = Run(**{k: v for k, v in payload.items() if k in campos})
    if rec.stage_reached not in ("stage2", "synthesis"):
        raise ResumeError("stage2_incomplete",
                          f"parcial parou em '{rec.stage_reached or '(sem estagio gravado)'}'"
                          " — so parcial com estagio 2 completo e retomavel")
    resposta_ok = [e.get("name") for e in rec.stage1 if e.get("ok")]
    elegiveis = [m for m in rec.members if m.get("name") in resposta_ok]
    falhas = [b.get("ranker", "?") for b in rec.stage2 if not b.get("ok")]
    # Parcial em modo lite nao e retomavel — e politica, nao acidente: o lite
    # roda menos avaliadores de proposito e --rank-lite e exclusivo com --resume
    # (cli.py). O que estava errado era o CODIGO: o estagio 2 de um parcial lite
    # esta COMPLETO para o modo em que rodou, e reprova-lo por "incompleto"
    # atribui a causa errada a quem le o erro. O comportamento nao muda —
    # fail-closed, reexecuta integral — muda o que ele diz.
    if rec.stage2_mode == "lite":
        raise ResumeError("stage2_lite",
                          f"parcial rodou o estagio 2 em modo lite "
                          f"({len(rec.stage2)} de {len(elegiveis)} avaliadores, por escolha "
                          f"do modo) — deliberacao nao plena nao e retomavel; reexecute integral")
    if len(rec.stage2) < len(elegiveis) or falhas:
        raise ResumeError("stage2_incomplete",
                          f"cedulas {len(rec.stage2)}/{len(elegiveis)} dos avaliadores elegiveis"
                          + (f", com falha: {falhas}" if falhas else ""))
    selado = (rec.producer or {}).get("config_sha256")
    atual = config_digest(cfg)
    if selado != atual:
        raise ResumeError("config_drift",
                          f"parcial selado com config {(selado or 'ausente')[:12]},"
                          f" atual {atual[:12]} — roster/config mudou desde a execucao")
    return rec, sha


def write_partial(rec: Run, runs_dir: Path, stage: str, elapsed_s: float) -> Path:
    """Grava o que ja foi pago ate este limite de estagio.

    O 'rec' vivo nao e mutado: vai a disco uma copia marcada, para que o
    registro final nasca limpo (partial=false) e leia igual ao historico. O
    parcial e reescrito a cada limite — nao e registro selado, e o rastro da
    execucao em voo; o final, esse sim, nunca se reescreve.

    A troca e atomica (grava em .tmp e renomeia): morte no meio da escrita
    deixaria o parcial truncado, apagando junto o limite anterior — que e
    justamente o que este mecanismo existe para salvar.
    """
    runs_dir.mkdir(parents=True, exist_ok=True)
    snap = replace(rec, partial=True, stage_reached=stage,
                   usage=_total_usage(rec), usage_by_stage=_usage_by_stage(rec),
                   elapsed_s=round(elapsed_s, 2))
    path = partial_path(runs_dir, rec.started_at,
                        resumed=rec.resumed_from is not None)
    payload = asdict(snap) | {"sha256": snap.digest()}
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def finalize_run(rec: Run, runs_dir: Path) -> Path:
    """Grava o registro final e so entao apaga o parcial DESTE processo.

    Nesta ordem: save_run que falha deixa o parcial em disco, que e tudo o que
    sobrou do que foi pago. Registro retomado (resumed_from): o parcial
    referenciado pertence a OUTRA execucao — outro carimbo, outro pid — e o
    nome aqui so endereca o rastro proprio; o referenciado nunca e removido
    (a secao 30 da suíte prova o arquivo intacto apos o resume).
    """
    path = save_run(rec, runs_dir)
    partial_path(runs_dir, rec.started_at,
                 resumed=rec.resumed_from is not None).unlink(missing_ok=True)
    return path


def save_run(rec: Run, runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    digest = rec.digest()
    stamp = stamp_for(rec.started_at)
    path = runs_dir / f"{stamp}-{digest[:12]}.json"
    # registro e imutavel: o mesmo sha ja gravado nao se reescreve (mtime prova)
    if path.is_file():
        return path
    payload = asdict(rec) | {"sha256": digest}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
