# Handoff — issue #10 (T9)
PR #25 · branch issue/10-cli-deliberate (código em f7dd08114e34) · 2026-08-26

## O que mudou no repo
- `council/cli.py`: subcomando `deliberate` (QUESTION, --profile obrigatório, --bundle CAMINHO|- com erro nomeado, --ref prefixo repetível resolvendo sha256 completo do registro mais recente que casa, --members/--chairman/--json/--quiet). Saída: `[STATUS] escolha — confiança` + dissidências/fundamentos (decider) ou síntese; audit in-memory com bundle vira aviso dim pós-execução apontando o comando de auditoria.
- `test_offline.py`: seção 23 (13 checks: E2E decider, registro, --json, erros exit 2 (perfil ausente/inexistente/ref substring/bundle ilegivel), --ref encadeado, --bundle -, decisao ilegivel nos dois modos).

## Decisões tomadas em voo (fora do plano)
- `--ref` casa por PREFIXO (startswith no sha256 ou sufixo do nome de arquivo); substring do meio é recusada; múltiplos casamentos → o mais recente por `started_at`.
- Predicado de sucesso único para texto e --json: decider exige decisão parseada; synthesizer, síntese ok.
- Exit codes: 0 = decisão (decider) ou síntese ok; 1 = execução rodou sem produzir decisão/síntese; 2 = erro de entrada (perfil/bundle/ref/members) nomeado.
- Audit in-memory é cortesia (try/except nunca derruba), mesmo padrão do `ask`.

## Pegadinhas descobertas
- Registros do mesmo segundo: nome de arquivo não ordena por tempo (sha desempata arbitrário) — testes localizam registro pelo campo `question`, nunca por sorted()[-1].
- O `--json` sair no stdout junto do registro salvo em runs_dir da config: tests patcham cfgmod.load (padrão seção 22).

## O que a próxima issue precisa saber
- Para #11 (MCP): a ferramenta `council_deliberate` monta a mesma `Deliberation` via `cfg.profiles[nome]`; exit-code semantics da CLI não se aplicam — MCP devolve `isError: true` com o mesmo texto nomeado.
- Para #12 (perfis reais): E2E da seção 23 é o molde — só trocar o perfil fixture pelos do council.toml real.
- Skill council-grill (#14) usará: `council deliberate "..." --profile grill --bundle <estado> --ref <sha-anterior>` encadeando rodadas.

## Pendências deixadas
- nenhuma
