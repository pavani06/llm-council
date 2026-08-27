# Handoff — issue #33 (C4)
PR #39 · branch issue/33-destilar-proposal (código em c5a4ac99efd7) · 2026-08-26

## O que mudou no repo
- `council/engine.py`: `_distill` trata `proposal` — `parse_proposal` por resposta cega; candidato é `f"{titulo}\n\n{corpo}"` (composição canônica); parse falho vira aviso nomeado `destilacao: <membro>: <erro>` e exclui o candidato, espelhando questions. Import de `parse_proposal`; docstrings de `_distill`/`Candidate` e o comentário da destilação no `run` atualizados. Nenhum prompt, ranking, alias ou presidente tocado.
- `test_offline.py`: seção 28 nova (12 checks) — fixture válido, cédula só com destilado, membro sem bloco, `TITULO` vazio. Fallbacks de estágio 1 das seções 21, 23, 24 e 26 passam a responder com bloco `PROPOSAL` válido (perfis `proposal` exigem; checks intocados). Suite 375 checks exit 0; golden (seção 15) byte a byte.

## Decisões tomadas em voo (fora do plano)
- **Composição do candidato: `titulo + "\n\n" + corpo`** — linha de título, linha vazia, corpo. Nomeada na diretiva; espelha o formato composto de questions (pergunta + Recomendação).
- **Fixtures das seções 21/23/24/26 adaptados, checks intocados**: os fallbacks respondiam estágio 1 em prosa para perfis `proposal`; antes de C4 viravam candidatos crus, agora seriam excluídos. O contrato do formato mudou — o fixture segue o contrato; nenhuma checagem foi editada, enfraquecida ou removida.
- **Caso (b2) usa `TITULO` vazio como segundo erro nomeado** (além de bloco ausente) para cobrir os dois erros nomeados no `parse_proposal` que o fluxo pode produzir.

## Pegadinhas descobertas
- A mudança de significado é retroativa só no teste: qualquer fixture futuro com perfil `proposal` DEVE responder estágio 1 com bloco `PROPOSAL` válido, senão o run sai sem candidatos (decider: "decisao impossivel"). Os quatro fallbacks adaptados marcam o caminho.
- `resposta inteira` segue em `rec.stage1[i].content` — o corpus do experimento ganhou a separação análise/proposta sem perder proveniência.

## O que a próxima issue precisa saber
- **#34 (C5)**: não depende deste campo; soma custo por `usage_by_stage`, nunca por `usage`.
- **Consumidores de `candidates[].text`**: em runs pós-C4 com perfil `proposal` o texto é a proposta destilada, não a resposta do conselheiro; resposta inteira está em `stage1[].content`. `id`/`author` seguem o membro: `decision_aliases`, `consensus[].member` e a auto-exclusão (`c.author == ranker.name`) funcionam sem cruzamento.
- Lista aditiva do schema até aqui: C1 `partial`/`stage_reached`/`interrupted`/`interruption_reason`; C2 `usage_by_stage` + `usage`/`latency_s` por cédula; C3 `decision_aliases`; **C4 nenhum campo novo** — muda o conteúdo de `candidates[].text` para runs novos com perfil `proposal`.

## Pendências deixadas
- Nenhuma.
