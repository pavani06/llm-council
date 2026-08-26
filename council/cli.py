"""CLI do conselho."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import config as cfgmod
from .engine import Council, save_run

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _progress(stage: str, msg: str) -> None:
    tag = {"stage1": "1 respostas", "stage2": "2 avaliacao cega", "stage3": "3 sintese"}.get(stage, stage)
    _err(f"{DIM}[{tag}]{RESET} {msg}")


# --------------------------------------------------------------------- ask


def cmd_ask(args) -> int:
    cfg = cfgmod.load(Path(args.config) if args.config else None)
    if args.members:
        wanted = {n.strip() for n in args.members.split(",")}
        cfg.members = [m for m in cfg.members if m.name in wanted]
        if not cfg.members:
            _err(f"nenhum conselheiro casa com --members={args.members}")
            return 2
    if args.chairman:
        match = [m for m in cfg.members if m.name == args.chairman]
        if match:
            cfg.chairman = match[0]
        else:
            _err(f"presidente '{args.chairman}' nao esta no conselho configurado")
            return 2

    question = args.question or sys.stdin.read().strip()
    if not question:
        _err("pergunta vazia")
        return 2

    council = Council(cfg, progress=None if args.quiet else _progress)
    rec = council.run(question, skip_ranking=args.no_rank)

    runs_dir = Path(cfg.settings.runs_dir)
    if not runs_dir.is_absolute():
        runs_dir = cfg.source.parent / runs_dir
    path = save_run(rec, runs_dir)

    if args.json:
        print(json.dumps(asdict(rec) | {"sha256": rec.digest()}, ensure_ascii=False, indent=2))
        return 0 if rec.synthesis.get("ok") else 1

    if not args.quiet:
        _err("")
        if rec.consensus:
            _err(f"{BOLD}consenso{RESET}")
            for c in rec.consensus:
                if not c["ballots"]:
                    continue
                bar = "#" * round(c["score"] * 20)
                _err(f"  {c['member']:<14} {c['score']:.2f} {DIM}{bar}{RESET}")
            if rec.divided:
                _err(f"  {DIM}conselho dividido — sem folga clara no topo{RESET}")
            _err("")

    print(rec.synthesis.get("content") or "(sem sintese)")

    if not args.quiet:
        u = rec.usage
        _err("")
        _err(
            f"{DIM}{rec.elapsed_s}s · {u.get('total_tokens', 0)} tokens · "
            f"registro {path.name} · sha256 {rec.digest()[:12]}{RESET}"
        )
        for w in rec.warnings:
            _err(f"{DIM}aviso: {w}{RESET}")
        try:
            from . import audit as ad
            from dataclasses import asdict as _asdict
            aud = ad.auditar(_asdict(rec))
            if aud.acrescimos:
                n = len(aud.acrescimos)
                _err(f"{DIM}o presidente usou termo que nenhuma resposta continha em "
                     f"{n} trecho(s) — 'council audit' para ver{RESET}")
        except Exception:
            pass  # a auditoria e cortesia; nunca pode derrubar a resposta
    return 0 if rec.synthesis.get("ok") else 1


# ------------------------------------------------------------------ doctor


def cmd_doctor(args) -> int:
    try:
        cfg = cfgmod.load(Path(args.config) if args.config else None)
    except Exception as e:
        print(f"config: FALHA — {e}")
        return 2
    print(f"config      {cfg.source}")
    envs = cfgmod.load_env_files()
    print(f".env        {', '.join(str(p) for p in envs) or '(nenhum encontrado)'}")
    print()
    print("provedores")
    for name in sorted(cfg.providers):
        key_env = cfg.key_env_for(name)
        ok = cfg.has_key(name)
        print(f"  {name:<10} {key_env:<22} {'chave presente' if ok else 'SEM CHAVE'}")
    faltando = []
    for name, spec in sorted(cfg.providers.items()):
        if spec.get("api") == "anthropic" and cfg.has_key(name):
            try:
                import anthropic  # noqa: F401
            except ImportError:
                faltando.append(name)
    if faltando:
        print()
        print(f"  provedor(es) {faltando} exigem o SDK 'anthropic', ausente neste interpretador.")
        print("  instale:  .venv/bin/python -m pip install -r requirements.txt")
        print("  (use ./bin/council, que prefere o venv do projeto)")

    print()
    print("conselho")
    active = {m.name for m in cfg.active_members()}
    for m in cfg.members:
        print(f"  {m.name:<14} {m.provider + '/' + m.model:<30} {'ativo' if m.name in active else 'inativo (sem chave)'}")
    ch = cfg.chairman
    inside = any(m.provider == ch.provider and m.model == ch.model for m in cfg.members)
    print(f"  {'presidente':<14} {ch.provider}/{ch.model}")
    print()
    n = len(active)
    if n == 0:
        print("BLOQUEADO: nenhum conselheiro com chave. Preencha o .env.")
        return 1
    if n < 3:
        print(f"AVISO: {n} conselheiro(s) ativo(s). Com auto-exclusao o estagio 2 exige 3+.")
    if inside:
        print("AVISO: o presidente tambem e conselheiro — ele julga a propria resposta na sintese.")
    if not cfg.has_key(ch.provider):
        print(f"BLOQUEADO: presidente sem chave ({cfg.key_env_for(ch.provider)}).")
        return 1
    from . import provenance
    commit, sujo = provenance.git_state()
    print()
    print("selo atual (o que um registro gerado agora carregaria)")
    print(f"  codigo   {provenance.code_digest()[:16]}")
    print(f"  config   {provenance.config_digest(cfg)[:16]}")
    print(f"  commit   {(commit or '-')[:12]}{' +SUJO' if sujo else ''}")
    print()
    print(f"pronto: {n} conselheiros ativos, presidente {'cego' if cfg.settings.blind_chairman else 'com identidades'}.")
    return 0


# ------------------------------------------------------------------ models


def cmd_models(args) -> int:
    cfg = cfgmod.load(Path(args.config) if args.config else None)
    targets = [args.provider] if args.provider else sorted(cfg.providers)
    rc = 0
    for name in targets:
        if not cfg.has_key(name):
            print(f"{name}: sem chave ({cfg.key_env_for(name)}), pulado")
            continue
        try:
            ids = cfg.endpoint(name).list_models()
            fonte = ""
        except Exception as e:
            known = cfg.known_models(name)
            if not known:
                print(f"{name}: FALHA — {e}")
                rc = 1
                continue
            ids = known
            fonte = "  [catalogo do council.toml; o endpoint nao expoe /models]"
        print(f"{name} ({len(ids)}):{fonte}")
        for i in ids:
            print(f"  {i}")
    return rc


# -------------------------------------------------------------------- show


def cmd_show(args) -> int:
    cfg = cfgmod.load(Path(args.config) if args.config else None)
    runs_dir = Path(cfg.settings.runs_dir)
    if not runs_dir.is_absolute():
        runs_dir = cfg.source.parent / runs_dir
    files = sorted(runs_dir.glob("*.json"))
    if not files:
        print("nenhum registro em " + str(runs_dir))
        return 1
    target = files[-1] if not args.sha else next((f for f in files if args.sha in f.name), None)
    if target is None:
        print(f"registro com sha '{args.sha}' nao encontrado")
        return 1
    data = json.loads(target.read_text(encoding="utf-8"))
    if args.raw:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print(f"{target.name}  ({data['started_at']}, {data['elapsed_s']}s)")
    print(f"pergunta: {data['question'][:200]}")

    selo = data.get("producer") or {}
    if selo:
        from . import provenance
        commit = (selo.get("git_commit") or "-")[:12]
        sujo = " +sujo" if selo.get("git_dirty") else ""
        print()
        print(f"produtor    council {selo.get('version','?')} · python {selo.get('python','?')}")
        print(f"            commit {commit}{sujo}")
        print(f"            codigo {selo.get('code_sha256','')[:12]}  config {selo.get('config_sha256','')[:12]}")
        for div in provenance.compare(selo):
            print(f"  DIVERGE   {div}")
    else:
        print()
        print("  (registro anterior ao selo de produtor — origem nao verificavel)")
    print()
    for c in data.get("consensus", []):
        print(f"  {c['member']:<14} {c['score']:.2f}  posicoes {c['positions']}")
    print()
    for b in data.get("stage2", []):
        print(f"  cedula de {b['ranker']}: {' > '.join(b['order_members']) or '(invalida)'}")
    print()
    print(data.get("synthesis", {}).get("content", "(sem sintese)"))
    return 0


# ----------------------------------------------------------------------- ab


def _dir_de(cfg, nome: str) -> Path:
    d = Path(getattr(cfg.settings, nome))
    return d if d.is_absolute() else cfg.source.parent / d


def cmd_ab(args) -> int:
    """Julgamento cego do operador: duas respostas, sem autoria, sem consenso."""
    import random as _random

    from . import judgment as jd
    from . import provenance

    cfg = cfgmod.load(Path(args.config) if args.config else None)
    try:
        caminho, rec = jd.carregar(_dir_de(cfg, "runs_dir"), args.sha)
        a, b, motivo = jd.escolher_par(rec, args.par)
        opcoes, slot_para_membro = jd.cegar(rec, (a, b), _random.SystemRandom())
    except jd.SemPar as e:
        _err(f"{e}")
        return 2

    print(f"{BOLD}registro{RESET} {caminho.name}  ·  sha {rec.get('sha256','')[:12]}")
    print(f"{DIM}{motivo}{RESET}")
    print()
    print(f"{BOLD}pergunta{RESET}")
    for linha in rec.get("question", "").strip().splitlines():
        print(f"  {linha}")
    print()

    for op in opcoes:
        print(f"{BOLD}{'─' * 72}{RESET}")
        print(f"{BOLD}OPÇÃO {op['slot']}{RESET}")
        print(f"{BOLD}{'─' * 72}{RESET}")
        print(op["texto"].strip())
        print()
    print(f"{BOLD}{'─' * 72}{RESET}")
    print(f"{DIM}autoria e consenso ficam ocultos até você escolher{RESET}")
    print()

    escolha = args.choose
    if escolha is None:
        try:
            escolha = input("sua escolha [1 / 2 / empate / nenhuma]: ").strip().lower()
        except EOFError:
            _err("\nsem terminal interativo — use --choose 1|2|empate|nenhuma")
            return 2
    if escolha not in jd.ESCOLHAS:
        _err(f"escolha inválida: {escolha!r} (use {', '.join(jd.ESCOLHAS)})")
        return 2

    nota = args.note
    if nota is None and args.choose is None:
        try:
            nota = input("por quê? (opcional, vai verbatim para o registro): ").strip()
        except EOFError:
            nota = ""
    nota = nota or ""

    from . import __version__
    try:
        destino, veredito = jd.gravar(
            _dir_de(cfg, "judgments_dir"), caminho, rec, slot_para_membro,
            escolha, nota, provenance.seal(cfg, __version__), refazer=args.redo,
        )
    except jd.JaJulgado as e:
        _err(f"\n{e}")
        return 3

    print()
    print(f"{BOLD}revelação{RESET}")
    for slot, membro in sorted(slot_para_membro.items()):
        score = jd.consenso_de(rec, membro)
        marca = "  ← sua escolha" if slot == escolha else ""
        s_txt = f"{score:.2f}" if score is not None else "  -"
        print(f"  opção {slot}: {membro:<12} consenso {s_txt}{marca}")

    conc = veredito["concorda_com_borda"]
    print()
    if conc is True:
        print(f"  {BOLD}você e o conselho concordaram.{RESET}")
    elif conc is False:
        print(f"  {BOLD}você discordou do conselho.{RESET} O Borda pôs o outro na frente.")
    else:
        print(f"  {DIM}sem comparação: empate no consenso, ou escolha sem lado.{RESET}")
    print(f"{DIM}veredito em {destino.name} · endereça o registro por sha256 · o registro não foi alterado{RESET}")
    return 0


def cmd_agreement(args) -> int:
    """Quantas vezes o julgamento cego do operador bateu com o Borda."""
    from . import judgment as jd

    cfg = cfgmod.load(Path(args.config) if args.config else None)
    r = jd.apurar(_dir_de(cfg, "judgments_dir"))

    if not r["total"]:
        print("nenhum veredito ainda. Rode: council ab")
        return 1

    print(f"vereditos            {r['total']}")
    print(f"comparáveis          {r['decididos']}")
    print(f"empates/abstenções   {r['empates_ou_abstencoes']}")
    if r["taxa"] is None:
        print("\nnenhum veredito comparável — nada a concluir.")
        return 0
    print(f"concordância         {r['acordos']}/{r['decididos']}  ({r['taxa'] * 100:.0f}%)")
    print()
    if r["decididos"] < 10:
        print(f"{DIM}n={r['decididos']} é pequeno demais para concluir qualquer coisa sobre o Borda.{RESET}")
        print(f"{DIM}Este número só começa a dizer algo com algumas dezenas de julgamentos.{RESET}")
    if args.list:
        print()
        for v in r["vereditos"]:
            sinal = {True: "concorda", False: "DISCORDA", None: "-"}[v.get("concorda_com_borda")]
            print(f"  {v['registro_sha256'][:12]}  {v['escolha']:<8} {sinal:<9} {v['pergunta'][:56]}")
    return 0


# ------------------------------------------------------------ deliberate


def cmd_deliberate(args) -> int:
    """Deliberacao com perfil: bundle + papeis + decisao estruturada."""
    from .engine import Deliberation

    cfg = cfgmod.load(Path(args.config) if args.config else None)
    if args.members:
        wanted = {n.strip() for n in args.members.split(",")}
        cfg.members = [m for m in cfg.members if m.name in wanted]
        if not cfg.members:
            _err(f"nenhum conselheiro casa com --members={args.members}")
            return 2
    if args.chairman:
        match = [m for m in cfg.members if m.name == args.chairman]
        if match:
            cfg.chairman = match[0]
        else:
            _err(f"presidente '{args.chairman}' nao esta no conselho configurado")
            return 2

    if not args.profile:
        _err("--profile e obrigatorio (o caso sem perfil e o proprio 'ask')")
        return 2
    perfil = cfg.profiles.get(args.profile)
    if perfil is None:
        disponiveis = ", ".join(sorted(cfg.profiles)) or "(nenhum definido no council.toml)"
        _err(f"perfil '{args.profile}' nao existe. Disponiveis: {disponiveis}")
        return 2

    if args.bundle == "-":
        bundle = sys.stdin.read()
    elif args.bundle:
        try:
            bundle = Path(args.bundle).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as e:
            _err(f"bundle ilegivel — {type(e).__name__}: {e}")
            return 2
    else:
        bundle = None

    runs_dir = Path(cfg.settings.runs_dir)
    if not runs_dir.is_absolute():
        runs_dir = cfg.source.parent / runs_dir
    refs = []
    if args.ref:
        registros = sorted(runs_dir.glob("*.json"))
        for prefixo in args.ref:
            casa = []
            for p in registros:
                r = json.loads(p.read_text(encoding="utf-8"))
                if p.stem.endswith(prefixo) or (r.get("sha256") or "").startswith(prefixo):
                    casa.append(r)
            if not casa:
                _err(f"--ref '{prefixo}' nao casa nenhum registro em {runs_dir}")
                return 2
            ultimo = max(casa, key=lambda r: r.get("started_at", ""))
            refs.append(ultimo["sha256"])
    question = args.question or sys.stdin.read().strip()
    if not question:
        _err("pergunta vazia")
        return 2

    council = Council(cfg, progress=None if args.quiet else _progress)
    rec = council.run(Deliberation(question, profile=perfil, bundle=bundle, run_refs=refs))

    if not runs_dir.exists():
        runs_dir.mkdir(parents=True, exist_ok=True)
    path = save_run(rec, runs_dir)

    # predicado unico de sucesso: decider exige decisao parseada; synthesizer,
    # sintese ok — nos dois modos de saida (texto e --json).
    sucesso = rec.decision is not None if perfil.chairman_mode == "decider" \
        else bool(rec.synthesis.get("ok"))

    if args.json:
        print(json.dumps(asdict(rec) | {"sha256": rec.digest()}, ensure_ascii=False, indent=2))
        return 0 if sucesso else 1

    if rec.decision:
        d = rec.decision
        print(f"[{d['status']}] {d['escolha']} — confiança {d['confianca']}")
        if d["dissidencias"] and d["dissidencias"].lower() != "nenhuma":
            print(f"dissidências: {d['dissidencias']}")
        print(f"fundamentos: {d['fundamentos']}")
    else:
        print(rec.synthesis.get("content") or "(sem síntese)")

    if not args.quiet:
        _err("")
        _err(f"{DIM}{rec.elapsed_s}s · {rec.usage.get('total_tokens', 0)} tokens · "
             f"registro {path.name} · sha256 {rec.digest()[:12]}{RESET}")
        for w in rec.warnings:
            _err(f"{DIM}aviso: {w}{RESET}")
        if bundle is not None:
            try:
                from . import audit as ad
                aud = ad.auditar(asdict(rec), bundle_text=bundle)
                if aud.acrescimos:
                    _err(f"{DIM}o presidente usou termo que nenhuma resposta/bundle continha em "
                         f"{len(aud.acrescimos)} trecho(s) — 'council audit {rec.digest()[:12]} "
                         f"--bundle {args.bundle}' para ver{RESET}")
            except Exception:
                pass  # cortesia; nunca derruba a deliberacao
    return 0 if sucesso else 1


# -------------------------------------------------------------------- audit


def cmd_audit(args) -> int:
    """O que a sintese afirma que nenhuma resposta continha."""
    import hashlib

    from . import audit as ad
    from . import judgment as jd

    cfg = cfgmod.load(Path(args.config) if args.config else None)
    try:
        caminho, rec = jd.carregar(_dir_de(cfg, "runs_dir"), args.sha)
    except jd.SemPar as e:
        _err(str(e))
        return 2

    bundle_text = None
    if args.bundle:
        if not rec.get("bundle_sha256"):
            _err("nao auditavel: registro sem bundle_sha256 — esta execucao nao usou bundle")
            return 2
        try:
            conteudo = Path(args.bundle).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as e:
            _err(f"nao auditavel: --bundle ilegivel — {type(e).__name__}: {e}")
            return 2
        sha = hashlib.sha256(conteudo.encode("utf-8")).hexdigest()
        if sha != rec["bundle_sha256"]:
            _err(
                "nao auditavel: bundle divergente — sha256 do arquivo nao bate com o "
                f"registro (arquivo {sha[:12]}, registro {rec['bundle_sha256'][:12]})"
            )
            return 2
        bundle_text = conteudo

    aud = ad.auditar(rec, bundle_text=bundle_text)
    print(f"{BOLD}registro{RESET} {caminho.name}  ·  sha {rec.get('sha256','')[:12]}")
    if aud.erro:
        _err(f"nao auditavel: {aud.erro}")
        return 2
    if rec.get("bundle_sha256") and not args.bundle:
        _err(f"{DIM}aviso: registro tem bundle (sha {rec['bundle_sha256'][:12]}) que nao foi "
             f"conferido — use --bundle CAMINHO para inclui-lo no corpus{RESET}")

    print(f"{DIM}{aud.frases_totais} frases na sintese · {aud.termos_sintese} termos conferiveis · "
          f"conselho: {', '.join(aud.membros)}{RESET}")
    print()

    if not aud.acrescimos:
        print("nenhum termo especifico da sintese esta ausente de todas as respostas.")
        print(f"{DIM}Isso NAO prova que a sintese e fiel: parafrase incorreta passa por aqui.{RESET}")
        return 0

    print(f"{BOLD}{len(aud.acrescimos)} trecho(s) com termo que nenhuma resposta continha{RESET}")
    print()
    for i, ac in enumerate(aud.acrescimos, start=1):
        print(f"  {BOLD}[{i}]{RESET} termos: {', '.join(ac.termos)}")
        for linha in _quebrar(ac.frase.strip(), 74):
            print(f"      {linha}")
        print()

    if args.verify:
        rc = _verificar(cfg, rec, aud)
        if rc:
            return rc

    print(f"{DIM}O prompt do presidente manda corrigir o conselho quando ele erra em bloco —{RESET}")
    print(f"{DIM}acrescimo pode ser a correcao pedida. Isto mostra o que ele pos por conta{RESET}")
    print(f"{DIM}propria; quem julga e voce.{RESET}")
    return 0


def _quebrar(texto: str, largura: int) -> list[str]:
    import textwrap
    return textwrap.wrap(" ".join(texto.split()), largura) or [""]


def _verificar(cfg, rec: dict, aud) -> int:
    """Uma chamada a um conselheiro que NAO e o presidente, sem saber o que audita."""
    from . import audit as ad

    chair = cfg.chairman
    candidatos = [m for m in cfg.active_members()
                  if not (m.provider == chair.provider and m.model == chair.model)]
    if not candidatos:
        _err("nenhum conselheiro disponivel que nao seja o presidente — verificacao pulada")
        return 0
    verificador = candidatos[0]

    _err(f"{DIM}verificando com {verificador.name} (cego, nao sabe que audita uma sintese)…{RESET}")
    ep = cfg.endpoint(verificador.provider)
    r = ep.chat(
        verificador.model,
        [{"role": "user", "content": ad.prompt_verificacao(rec, aud)}],
        temperature=cfg.settings.temperature, max_tokens=cfg.settings.max_tokens,
        timeout=cfg.settings.timeout, retries=cfg.settings.retries, params=verificador.params,
    )
    if not r.ok:
        _err(f"verificacao falhou: {r.error}")
        return 0

    vered = ad.parse_verificacao(r.content, len(aud.acrescimos))
    if not vered:
        _err("verificador nao respondeu no formato esperado; ficam so os candidatos acima")
        return 0

    print(f"{BOLD}verificacao por {verificador.name}{RESET}")
    for i, ac in enumerate(aud.acrescimos, start=1):
        estado, motivo = vered.get(i, ("?", "sem veredito"))
        marca = f"{BOLD}ACRESCIMO{RESET}" if estado == "ACRESCIMO" else "sustentada"
        print(f"  [{i}] {marca} — {motivo}")
    print()
    return 0


# --------------------------------------------------------------------- main


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="council", description="Conselho de LLMs com avaliacao cruzada cega.")
    p.add_argument("--config", help="caminho de um council.toml alternativo")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ask", help="faz uma pergunta ao conselho")
    a.add_argument("question", nargs="?", help="a pergunta (ou stdin)")
    a.add_argument("--members", help="subconjunto por nome, separado por virgula")
    a.add_argument("--chairman", help="usa este conselheiro como presidente")
    a.add_argument("--no-rank", action="store_true", help="pula o estagio 2 (mais barato e rapido)")
    a.add_argument("--json", action="store_true", help="registro completo em JSON no stdout")
    a.add_argument("--quiet", action="store_true", help="so a resposta final")
    a.set_defaults(func=cmd_ask)

    dl = sub.add_parser("deliberate", help="deliberacao com perfil: bundle, papeis e decisao")
    dl.add_argument("question", nargs="?", help="a pergunta (ou stdin)")
    dl.add_argument("--profile", help="nome do perfil em [profiles] do council.toml")
    dl.add_argument("--bundle", help="arquivo de evidencia da deliberacao, ou - para stdin")
    dl.add_argument("--ref", action="append", help="prefixo de sha de deliberacao anterior (repetivel)")
    dl.add_argument("--members", help="subconjunto por nome, separado por virgula")
    dl.add_argument("--chairman", help="usa este conselheiro como presidente")
    dl.add_argument("--json", action="store_true", help="registro completo em JSON no stdout")
    dl.add_argument("--quiet", action="store_true", help="so a decisao/sintese final")
    dl.set_defaults(func=cmd_deliberate)

    d = sub.add_parser("doctor", help="verifica config, chaves e coerencia do conselho")
    d.set_defaults(func=cmd_doctor)

    m = sub.add_parser("models", help="lista modelos reais de cada provedor")
    m.add_argument("provider", nargs="?", help="limita a um provedor")
    m.set_defaults(func=cmd_models)

    ab = sub.add_parser("ab", help="julgamento cego seu: duas respostas, sem autoria")
    ab.add_argument("sha", nargs="?", help="prefixo do sha256 do registro; sem isso, o mais recente")
    ab.add_argument("--par", help="dois conselheiros por nome, separados por virgula")
    ab.add_argument("--choose", choices=["1", "2", "empate", "nenhuma"], help="nao interativo")
    ab.add_argument("--note", help="seu verbatim sobre a escolha")
    ab.add_argument("--redo", action="store_true",
                    help="substitui um veredito existente; o anterior fica encadeado dentro do novo")
    ab.set_defaults(func=cmd_ab)

    au = sub.add_parser("audit", help="o que a sintese afirma que ninguem sustentou")
    au.add_argument("sha", nargs="?", help="prefixo do sha256; sem isso, o mais recente")
    au.add_argument("--bundle", help="arquivo do bundle da execucao; sha256 e conferido contra o registro")
    au.add_argument("--verify", action="store_true",
                    help="confere os candidatos com um conselheiro que nao e o presidente (1 chamada)")
    au.set_defaults(func=cmd_audit)

    ag = sub.add_parser("agreement", help="taxa de concordancia entre voce e o Borda")
    ag.add_argument("--list", action="store_true", help="lista veredito a veredito")
    ag.set_defaults(func=cmd_agreement)

    s = sub.add_parser("show", help="mostra um registro salvo")
    s.add_argument("sha", nargs="?", help="prefixo do sha256; sem isso, o mais recente")
    s.add_argument("--raw", action="store_true", help="JSON cru")
    s.set_defaults(func=cmd_show)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        _err("\ninterrompido")
        return 130
    except (FileNotFoundError, ValueError, KeyError) as e:
        _err(f"erro de configuracao: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
