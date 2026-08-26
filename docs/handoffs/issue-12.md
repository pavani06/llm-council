# Handoff — issue #12 (T11)
PR #<n> · branch issue/12-perfis-reais (código em 4df0a0cd2783) · 2026-08-26

## O que mudou no repo
- `council.toml`: perfis reais `[profiles.continuation]` (decider/proposal; gpt=continuador, claude=auditor, deepseek=guardião de escopo, glm deliberadamente SEM papel; 4 criteria) e `[profiles.grill]` (synthesizer/questions; 4 lentes; 4 criteria) + comentário de custo GLM.
- `council/cli.py`: doctor lista perfis (nome, modo/formato, nº papeis) ou "(nenhum perfil definido)".
- `test_offline.py`: seção 25 (12 checks: carga dos perfis, papéis/criteria, E2E continuation com decisão, E2E grill com 8 questões, doctor).

## Decisões tomadas em voo (fora do plano)
- **Uma checagem existente editada (primeira do épico, declarada)**: seção 16 "council.toml atual (sem perfis) carrega com profiles vazio" — a premissa foi invalidada POR ESTA issue (perfis reais agora existem). Intenção preservada com fixture inline SEM_PERFIS; comentário no teste registra a razão.
- Roles como sub-tabelas `[profiles.X.roles]` (inline table multilinha não é TOML válido); criteria como array multilinha direto na tabela.

## Pegadinhas descobertas
- TOML 1.0: inline table não aceita `\` de continuação — roles longos viram sub-tabela.
- `doctor` na worktree reclama de .env (ambiente); validar na árvore principal.

## O que a próxima issue precisa saber
- Para #15 (smoke pago): usar `--profile continuation` com bundle real; o E2E da seção 25 é o comportamento esperado (decisão DECIDIDO/ENCALHADO no JSON).
- Para #14 (skill council-grill): `--profile grill` pronto; cada rodada devolve até 4×5 questões candidatas.
- `council deliberate --profile continuation "..." --bundle X --ref Y` está operacional ponta a ponta (CLI #10 + perfis reais).

## Pendências deixadas
- nenhuma
