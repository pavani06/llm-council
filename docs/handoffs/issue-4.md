# Handoff — issue #4 (T2)
PR #19 · branch issue/4-config-perfis (código em c5eedc93fb24) · 2026-08-25

## O que mudou no repo
- `council/config.py`: dataclass `Profile`, constantes `CHAIRMAN_MODES`/`STAGE1_FORMATS`, `_profile()` validador, `Config.profiles`, parsing de `[profiles.<nome>]`, TOML inválido re-empacotado como `ValueError` nomeado.
- `test_offline.py`: seção 16 (12 checks: válido, defaults de tabela vazia, 7 inválidos nomeados, council.toml real sem perfis).

## Decisões tomadas em voo (fora do plano)
- `Profile.criteria: list[str] | None = None` — None = "não declarado"; o default (os 4 literais atuais) será resolvido na fronteira dos prompts (#5, `DEFAULT_CRITERIA` em prompts.py como fonte única). Evita duplicar os literais e derivar do golden.
- Perfil duplicado: o próprio `tomllib` recusa; `load()` re-empacota `TOMLDecodeError` como `ValueError("{path}: TOML invalido — ...")` — traceback cru de parser não é falha nomeada.
- Constantes exportadas (`CHAIRMAN_MODES`, `STAGE1_FORMATS`) para não haver segunda cópia das listas válidas.

## Pegadinhas descobertas
- `CONFIG_CANDIDATES` é avaliado no import-time: setar `COUNCIL_CONFIG` depois do import não muda o config achado. Testes de config devem passar `load(path)` explícito.
- Worktree não tem `.env` (ignorado pelo git): `council doctor` falha por ambiente na worktree — validar doctor na árvore principal após o merge.

## O que a próxima issue precisa saber
- Contrato `Profile` para #5/#6/#8: `name`, `roles: dict[membro→texto]` (só nomes que existem no council), `criteria: list|None` (None = default dos prompts), `chairman_mode ∈ {"synthesizer","decider"}`, `stage1_format ∈ {"prose","questions","proposal"}`; acesso por `cfg.profiles[nome]` (dict vazio quando sem perfis).
- #5: `DEFAULT_CRITERIA` deve renderizar byte-idêntico ao bloco "Criterios" de `golden/ranking.txt` (handoff da #2); o golden continua sendo a prova.
- #8: perfis ainda NÃO entram no selo (`config_snapshot` intocado) — é passo seu.

## Pendências deixadas
- nenhuma
