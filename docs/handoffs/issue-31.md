# Handoff — issue #31 (C2)
PR #37 · branch issue/31-custo-estagio2 (código em 7a4fe2a24676) · 2026-08-26

## O que mudou no repo
- `council/ranking.py`: `Ballot` ganha `usage: dict | None` e `latency_s: float | None` ao fim, defaults `None`.
- `council/engine.py`: `_rank_one` preenche os dois no construtor da cédula, antes do teste de `reply.ok` — cédula falhada carrega o que o provedor reportou; a linha de progresso do estágio 2 ganha `(Xs, N tok)` no formato do estágio 1. Entradas de `rec.stage2` ganham as chaves `usage` e `latency_s`.
- `council/engine.py`: `Run.usage_by_stage` (aditivo, default `{}`) com `stage1`/`stage2`/`synthesis`/`total`; helper `_somar_usage` extraído, usado por `_total_usage` (mesmo resultado de sempre) e por `_usage_by_stage`; preenchido no fim de `run`, no retorno antecipado do decider sem candidatos, e no snapshot do parcial.
- `test_offline.py`: seção 27, 14 checks, casos (a)-(e). Suite 351 checks exit 0; golden (seção 15) byte a byte.

## Decisões tomadas em voo (fora do plano)
- **`_somar_usage` extraído** em vez de escrever a soma duas vezes: a identidade aritmética do critério 2 (`total == stage1+stage2+synthesis`) passa a ser estrutural, não coincidência de duas contas à mão. `_total_usage` mudou de corpo, nunca de resultado — o critério 3 prova por igualdade contra a conta antiga replicada no teste.
- **Cédula sem chamada fica `None`, não zero.** A cédula inválida por auto-exclusão (`engine.py:218-224`) nunca chama o provedor; `None` diz "não houve chamada" enquanto `0` diria "custou zero". C5 depende dessa distinção para não contar chamada que não existiu.
- **O parcial de C1 também carrega `usage_by_stage`.** Sem isso o parcial mentiria por omissão: ele existe para o custo pago sobreviver à morte do processo, e a decomposição é justamente a parte do custo que estava invisível.
- **Retorno antecipado do decider sem candidatos** também preenche `usage_by_stage`: onde `rec.usage` é computado, a decomposição acompanha, senão o registro sai com um preenchido e o outro vazio.
- **Fixture de registro velho é sintético** (formato da seção 13): `runs/` é gitignored e não existe no CI. O registro real pré-C2 foi conferido no QA manual, não na suíte.

## Pegadinhas descobertas
- O rodapé do `council ask` continua mostrando o `usage` histórico (110 tokens no QA, contra 3390 reais) — é o comportamento pedido pela issue, não um bug: o campo mantém o significado e a verdade completa vive no `usage_by_stage`. Quem for exibir custo ao usuário (C5) tem de ler o campo novo.
- Um `Reply` de falha traz `latency_s` sempre e `usage` como o provedor deu (zeros quando não reportou) — por isso a cédula falhada tem custo gravado, mas nem sempre não-nulo.

## O que a próxima issue precisa saber
- **#32 (C3)** mexe no mesmo trecho do estágio 3 (`alias_decisao`, hoje em `engine.py:463-483`); não há conflito com esta issue, que não toca aliases.
- **#34 (C5)** já tem os dois blockers resolvidos depois desta. Para o ledger: some por `usage_by_stage.total`, nunca por `usage`; trate `usage_by_stage == {}` como registro anterior a C2 (custo do estágio 2 não recuperável); e trate cédula com `usage is None` como chamada que não aconteceu.
- Lista aditiva do schema até aqui: `partial`, `stage_reached`, `interrupted`, `interruption_reason` (C1), `usage_by_stage` no `Run` e `usage`/`latency_s` por cédula em `stage2` (C2).

## Pendências deixadas
- Latência por tentativa de retry segue sem registro (fora de escopo declarado na issue): `Reply.attempts` existe, mas o tempo de cada tentativa não é decomposto.
