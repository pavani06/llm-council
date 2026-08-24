"""Selo do produtor: o que gerou este registro.

Um registro sem isto e ininterpretavel depois de qualquer edicao — nao da para
saber qual prompt gerou aquela cedula, nem qual roster estava valendo. Com o
commit e o hash do codigo, o prompt de cada estagio e reconstituivel a partir
das respostas guardadas, sem precisar duplicar texto no arquivo.

Modulo folha de proposito: nao importa nada do projeto.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PKG = Path(__file__).resolve().parent
REPO = PKG.parent


def code_digest(pkg_dir: Path = PKG) -> str:
    """sha256 sobre todo o fonte do pacote, em ordem estavel.

    Cobre prompts.py, ranking.py, engine.py e providers.py de uma vez: qualquer
    edicao que mude o comportamento muda este hash.
    """
    h = hashlib.sha256()
    for path in sorted(pkg_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        h.update(path.relative_to(pkg_dir).as_posix().encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def git_state(repo_dir: Path = REPO) -> tuple[str | None, bool | None]:
    """(commit, sujo). (None, None) se nao houver git — nao e erro, e ausencia.

    'sujo' importa tanto quanto o commit: um sha com arvore suja nao endereca
    o que rodou de fato.
    """

    def run(*args: str) -> str | None:
        try:
            r = subprocess.run(
                ["git", "-C", str(repo_dir), *args],
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    commit = run("rev-parse", "HEAD")
    if commit is None:
        return None, None
    status = run("status", "--porcelain")
    return commit, bool(status) if status is not None else None


# Lista explicita do que entra no retrato da config. Allow-list, nao dump: o
# arquivo vai para o disco e pode ser compartilhado, entao nada entra por acaso.
_PROVIDER_FIELDS = ("base_url", "api", "api_key_env", "max_tokens_field",
                    "unsupported", "known_models")


def config_snapshot(cfg: Any) -> dict[str, Any]:
    """Config RESOLVIDA — inclui overrides de linha de comando, ao contrario do TOML.

    Guarda o NOME da variavel de ambiente da chave, nunca o valor.
    """
    return {
        "providers": {
            nome: {c: spec[c] for c in _PROVIDER_FIELDS if c in spec}
            for nome, spec in sorted(cfg.providers.items())
        },
        "council": [
            {"name": m.name, "provider": m.provider, "model": m.model, "params": m.params}
            for m in cfg.members
        ],
        "chairman": {
            "name": cfg.chairman.name, "provider": cfg.chairman.provider,
            "model": cfg.chairman.model, "params": cfg.chairman.params,
        },
        "settings": dict(sorted(vars(cfg.settings).items())),
    }


def config_digest(cfg: Any) -> str:
    blob = json.dumps(config_snapshot(cfg), sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()


def seal(cfg: Any, version: str) -> dict[str, Any]:
    """O bloco que vai para dentro do registro."""
    commit, sujo = git_state()
    return {
        "version": version,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "git_commit": commit,
        "git_dirty": sujo,
        "code_sha256": code_digest(),
        "config_sha256": config_digest(cfg),
        "config_source": str(getattr(cfg, "source", "")),
        "config": config_snapshot(cfg),
    }


def compare(selo: dict[str, Any]) -> list[str]:
    """Divergencias entre o selo de um registro e o estado atual da arvore."""
    fora = []
    atual_code = code_digest()
    if selo.get("code_sha256") and selo["code_sha256"] != atual_code:
        fora.append(
            f"codigo mudou desde a execucao (registro {selo['code_sha256'][:12]}, "
            f"atual {atual_code[:12]})"
        )
    commit, sujo = git_state()
    if selo.get("git_commit") and commit and selo["git_commit"] != commit:
        fora.append(f"outro commit (registro {selo['git_commit'][:12]}, atual {commit[:12]})")
    if selo.get("git_dirty"):
        fora.append("arvore estava SUJA na execucao — o commit registrado nao a endereca por inteiro")
    return fora
