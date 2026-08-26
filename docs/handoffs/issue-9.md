# Handoff — issue #9 (T8)
PR #24 · branch issue/9-audit-bundle (código em 5030dedb9f20) · 2026-08-26

## O que mudou no repo
- `council/audit.py`: `auditar(rec, bundle_text=None)` — corpus inclui bundle; bundle em registro sem `bundle_sha256` → erro nomeado (grounding fictício).
- `council/cli.py`: `council audit --bundle CAMINHO` — confere `sha256(arquivo) == rec.bundle_sha256`; divergente → exit 2 nomeado; registro com bundle sem flag → aviso dim "nao foi conferido".
- `test_offline.py`: seção 22 (10 checks: corpus, erro nomeado, 4 casos de CLI com exit codes).

## Decisões tomadas em voo (fora do plano)
- Semântica em duas camadas: `auditar()` confia no caller para o hash (docstring documenta); a VERIFICAÇÃO vive na CLI, que é a fronteira com arquivo. Registro sem bundle + flag = erro (exit 2), não aviso — auditar com bundle de outra execução não faz sentido.
- Aviso "nao foi conferido" é dim (stderr), auditoria segue parcial (rc 0): comportamento atual preservado para registros antigos.

## Pegadinhas descobertas
- `cmd_audit` carrega config PRÓPRIA (`args.config`) — teste de CLI precisa patchar `cfgmod.load` (padrão da suite para Endpoint.chat).

## O que a próxima issue precisa saber
- Para #10 (CLI deliberate): reusar o padrão do teste de CLI da seção 22 (`_Args` + `redirect_stderr` + patch de `cfgmod.load`); `council audit --bundle` é como o #15/skill conferem grounding de uma deliberação real.
- Exit codes do audit: 0 auditou (com ou sem aviso dim), 2 não-auditável (sem sintese/respostas/bundle errado/divergente).

## Pendências deixadas
- nenhuma
