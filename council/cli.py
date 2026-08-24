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
    print()
    for c in data.get("consensus", []):
        print(f"  {c['member']:<14} {c['score']:.2f}  posicoes {c['positions']}")
    print()
    for b in data.get("stage2", []):
        print(f"  cedula de {b['ranker']}: {' > '.join(b['order_members']) or '(invalida)'}")
    print()
    print(data.get("synthesis", {}).get("content", "(sem sintese)"))
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

    d = sub.add_parser("doctor", help="verifica config, chaves e coerencia do conselho")
    d.set_defaults(func=cmd_doctor)

    m = sub.add_parser("models", help="lista modelos reais de cada provedor")
    m.add_argument("provider", nargs="?", help="limita a um provedor")
    m.set_defaults(func=cmd_models)

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
