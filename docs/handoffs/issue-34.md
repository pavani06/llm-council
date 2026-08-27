# Handoff — issue #34 (C5)
PR #40 · branch issue/34-cost-ledger (código em a698a2c099ea) · 2026-08-26

## O que mudou no repo
- `council/cost.py` (novo, folha, só stdlib, não importa engine): `ledger(runs_dir)` acumula por provedor/modelo chamadas e prompt/completion/total tokens, final e parcial separados (classificação por sufixo `-partial.json`); registro pré-C2 entra com cédulas contadas e tokens do estágio 2 subcontados + nota nomeada. `estimate(cfg, runs_dir, profile)` deriva chamadas por provedor da config (stage1 por membro; cédula por respondente se N≥3; 1 do presidente) e tokens das medianas por estágio dos registros finais; `SemHistorico` (exceção nomeada) se qualquer estágio da estimativa não tem chamada observada.
- `council/cli.py`: `cmd_cost` + subcomando `cost` (`--estimate`, `--json`, `--profile`, `--members`, `--chairman`); overrides espelham `ask`/`deliberate`; exit 3 = estimativa impossível por falta de histórico (mensagem nomeada, nenhum número no stdout).
- `test_offline.py`: seção 29, 18 checks — ledger contra soma manual (final+parcial+antigo), estimativa com histórico (aritmética da config, medianas identificadas, cota glm=2), N=2 pula estágio 2, perfil inexistente exit 2, sem histórico exit 3. Suite 393 checks exit 0; golden (seção 15) byte a byte.

## Decisões tomadas em voo (fora do plano)
- **Parciais entram contabilizados como parciais** (nunca como finais): reconcilia o aviso do handoff da #30 ("use `final_runs`") com o pedido explícito da issue ("inclusive parciais... separando").
- **Medianas só sobre registros finais**: parcial é gasto truncado, não amostra representativa de estágio.
- **Pré-C2 contribui para medianas de stage1/synthesis** (usage sempre existiu nesses estágios); só as amostras de cédula exigem registro pós-C2 — sem desperdiçar histórico válido.
- **Suposições nomeadas no output**: todos respondem; ≥1 candidato válido por respondente (gate N≥3); presidente 1 chamada no caminho normal.

## Rodadas de review (oracle, no mesmo PR)
- R1 FAIL: estimate usava cfg.members (chamadas fantasma) e silenciava historico ilegivel — corrigido.
- R2 FAIL: zero ativos inventava chamada do presidente; SemHistorico descartava notas — corrigido.
- R3 FAIL: suposição presidencial contradizia o caso zero-ativos — corrigido (suposição só com membros).
- R4 PASS: handoff conferido (números finais: 18 checks, suite 393).

## Pegadinhas descobertas
- A cédula inválida por auto-exclusão (C2) tem `usage=None` = não houve chamada — o ledger conta por `usage is not None`, não por entrada; a pré-C2 conta por entrada (chamada existiu, tokens não).
- Provedor da cédula não está no registro: join `ranker` → `members[]`; cédula órfã vira nota nomeada, fora do ledger.

## O que a próxima issue precisa saber
- `council cost` é a fonte de custo para o operador; `usage_by_stage == {}` segue o contrato da C2 (antigo = subcontagem nomeada).
- Lista aditiva do schema até aqui: C1 `partial`/`stage_reached`/`interrupted`/`interruption_reason`; C2 `usage_by_stage` + `usage`/`latency_s` por cédula; C3 `decision_aliases`; C4 nenhum campo novo; **C5 nenhum campo novo** (tooling de leitura; engine intocado).

## Pendências deixadas
- Nenhuma. (review: 3 correções absorvidas no mesmo PR; detalhes na seção de rodadas)
