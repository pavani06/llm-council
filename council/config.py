"""Carga de configuracao: council.toml + .env. Somente stdlib."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .providers import ENDPOINT_TYPES, Endpoint

ROOT = Path(__file__).resolve().parent.parent
CONFIG_CANDIDATES = [
    Path(os.environ.get("COUNCIL_CONFIG", "")) if os.environ.get("COUNCIL_CONFIG") else None,
    Path.home() / ".config" / "council" / "council.toml",
    ROOT / "council.toml",
]
ENV_CANDIDATES = [
    Path.home() / ".config" / "council" / ".env",
    ROOT / ".env",
]


def load_env_files() -> list[Path]:
    """Le KEY=VALUE dos .env conhecidos para o ambiente. Nao sobrescreve o que ja existe."""
    loaded = []
    for path in ENV_CANDIDATES:
        if not path.is_file():
            continue
        loaded.append(path)
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            val = val.strip().strip('"').strip("'")
            # Sobrescreve variavel existente que esteja VAZIA: um export em branco no
            # .bashrc nao deve mascarar a chave real do .env (era o que acontecia aqui).
            if key and val and not os.environ.get(key, "").strip():
                os.environ[key] = val
    return loaded


@dataclass
class Member:
    name: str
    provider: str
    model: str
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.name} ({self.provider}/{self.model})"


# Modos/formatos validos; duplicar essas listas em outro lugar e deriva silenciosa.
CHAIRMAN_MODES = ("synthesizer", "decider")
STAGE1_FORMATS = ("prose", "questions", "proposal")


@dataclass
class Profile:
    """Perfil de deliberacao: papeis por conselheiro, criterios de julgamento,
    modo do presidente e formato do estagio 1.

    criteria=None significa "nao declarado": o default (os 4 criterios atuais
    dos prompts) e resolvido na fronteira dos prompts — fonte unica, sem copia.
    """

    name: str
    roles: dict[str, str] = field(default_factory=dict)
    criteria: list[str] | None = None
    chairman_mode: str = "synthesizer"
    stage1_format: str = "prose"


@dataclass
class Settings:
    exclude_self_rank: bool = True
    blind_chairman: bool = True
    shuffle_labels: bool = True
    timeout: float = 180.0
    max_tokens: int = 4096
    temperature: float = 0.3
    chairman_max_tokens: int = 8192
    retries: int = 2
    seed: int = 0
    scrub_identity: bool = True
    identity_terms: list[str] = field(default_factory=list)
    runs_dir: str = "runs"
    judgments_dir: str = "judgments"


@dataclass
class Config:
    providers: dict[str, dict[str, Any]]
    members: list[Member]
    chairman: Member
    settings: Settings
    source: Path
    profiles: dict[str, Profile] = field(default_factory=dict)

    def endpoint(self, provider: str) -> Endpoint:
        spec = self.providers.get(provider)
        if spec is None:
            raise KeyError(f"provedor '{provider}' nao esta em [providers] de {self.source}")
        key_env = spec.get("api_key_env", f"{provider.upper()}_API_KEY")
        api = spec.get("api", "openai")
        if api not in ENDPOINT_TYPES:
            raise ValueError(f"provedor '{provider}': api='{api}' desconhecida (use {sorted(ENDPOINT_TYPES)})")
        return ENDPOINT_TYPES[api](
            name=provider,
            base_url=spec["base_url"],
            api_key=os.environ.get(key_env),
            headers=spec.get("headers"),
            max_tokens_field=spec.get("max_tokens_field", "max_tokens"),
            unsupported=tuple(spec.get("unsupported", ())),
        )

    def key_env_for(self, provider: str) -> str:
        spec = self.providers.get(provider, {})
        return spec.get("api_key_env", f"{provider.upper()}_API_KEY")

    def known_models(self, provider: str) -> list[str]:
        """Catalogo declarado no TOML, usado quando o endpoint nao expoe /models."""
        return list(self.providers.get(provider, {}).get("known_models", []))

    def has_key(self, provider: str) -> bool:
        return bool(os.environ.get(self.key_env_for(provider)))

    def active_members(self) -> list[Member]:
        return [m for m in self.members if self.has_key(m.provider)]


def find_config() -> Path:
    for cand in CONFIG_CANDIDATES:
        if cand and cand.is_file():
            return cand
    raise FileNotFoundError(
        "council.toml nao encontrado. Procurado em: "
        + ", ".join(str(c) for c in CONFIG_CANDIDATES if c)
    )


def _member(raw: dict, what: str) -> Member:
    for req in ("provider", "model"):
        if req not in raw:
            raise ValueError(f"{what}: falta o campo obrigatorio '{req}'")
    return Member(
        name=raw.get("name") or raw["model"],
        provider=raw["provider"],
        model=raw["model"],
        params=raw.get("params", {}),
    )


_PROFILE_KEYS = ("roles", "criteria", "chairman_mode", "stage1_format")


def _profile(name: str, raw: dict, member_names: set[str]) -> Profile:
    onde = f"[profiles.{name}]"
    desconhecidas = set(raw) - set(_PROFILE_KEYS)
    if desconhecidas:
        raise ValueError(f"{onde}: chave(s) desconhecida(s): {sorted(desconhecidas)}")

    roles_raw = raw.get("roles")
    if roles_raw is None:
        roles = {}
    elif isinstance(roles_raw, dict):
        for quem, texto in roles_raw.items():
            if not isinstance(texto, str) or not texto.strip():
                raise ValueError(f"{onde}: papel de '{quem}' deve ser texto nao vazio")
        roles = dict(roles_raw)
    else:
        raise ValueError(
            f"{onde}: roles deve ser uma tabela membro -> texto, "
            f"nao {type(roles_raw).__name__}"
        )
    for quem in roles:
        if quem not in member_names:
            raise ValueError(
                f"{onde}: papel refere conselheiro inexistente '{quem}' "
                f"(disponiveis: {sorted(member_names)})"
            )

    criteria = raw.get("criteria")
    if criteria is not None:
        if isinstance(criteria, str) or not isinstance(criteria, list):
            raise ValueError(f"{onde}: criteria deve ser uma lista de textos")
        for item in criteria:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{onde}: criteria so aceita textos nao vazios")
        if not (1 <= len(criteria) <= 7):
            raise ValueError(f"{onde}: criteria deve ter de 1 a 7 itens (tem {len(criteria)})")

    mode = raw.get("chairman_mode", "synthesizer")
    if mode not in CHAIRMAN_MODES:
        raise ValueError(f"{onde}: chairman_mode '{mode}' invalido (use {' ou '.join(CHAIRMAN_MODES)})")

    fmt = raw.get("stage1_format", "prose")
    if fmt not in STAGE1_FORMATS:
        raise ValueError(f"{onde}: stage1_format '{fmt}' invalido (use {' ou '.join(STAGE1_FORMATS)})")

    return Profile(
        name=name,
        roles=roles,
        criteria=list(criteria) if criteria is not None else None,
        chairman_mode=mode,
        stage1_format=fmt,
    )


def load(path: Path | None = None) -> Config:
    load_env_files()
    path = path or find_config()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        # traceback cru de parser nao e falha nomeada; perfil duplicado cai aqui.
        raise ValueError(f"{path}: TOML invalido — {e}") from None

    providers = data.get("providers") or {}
    if not providers:
        raise ValueError(f"{path}: secao [providers] vazia")

    raw_members = data.get("council") or []
    if not raw_members:
        raise ValueError(f"{path}: nenhum [[council]] definido")
    members = [_member(m, f"[[council]] #{i + 1}") for i, m in enumerate(raw_members)]

    names = [m.name for m in members]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        raise ValueError(f"{path}: nomes de conselheiro duplicados: {sorted(dup)}")

    raw_chair = data.get("chairman")
    if not raw_chair:
        raise ValueError(f"{path}: secao [chairman] ausente")
    chairman = _member(raw_chair, "[chairman]")

    s = data.get("settings") or {}
    known = Settings().__dict__.keys()
    unknown = set(s) - set(known)
    if unknown:
        raise ValueError(f"{path}: settings desconhecidos: {sorted(unknown)}")
    settings = Settings(**s)

    if "profiles" in data:
        raw_profiles = data["profiles"]
        if not isinstance(raw_profiles, dict):
            # 'or {}' aqui engoliria profiles = "" / [] / false / 0 sem reclamar.
            raise ValueError(
                f"{path}: [profiles] deve ser uma tabela de perfis, "
                f"nao {type(raw_profiles).__name__}"
            )
    else:
        raw_profiles = {}
    member_names = {m.name for m in members}
    profiles: dict[str, Profile] = {}
    for nome, raw in raw_profiles.items():
        if not isinstance(raw, dict):
            raise ValueError(
                f"{path}: [profiles.{nome}] deve ser uma tabela, "
                f"nao {type(raw).__name__}"
            )
        profiles[nome] = _profile(nome, raw, member_names)

    return Config(
        providers=providers,
        members=members,
        chairman=chairman,
        settings=settings,
        source=path,
        profiles=profiles,
    )
