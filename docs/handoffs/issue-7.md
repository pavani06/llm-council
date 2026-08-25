# Handoff — issue #7 (T6)
PR #22 · branch issue/7-candidatos (código em fdddcfa19aed) · 2026-08-25

## O que mudou no repo
- `council/engine.py`: `Candidate(id, text, author)`, `_distill()` (scrubado→candidatos), `stage2`/`_rank_one` sobre candidatos com `exclude_self_rank` por author, criteria do perfil no ranking, `borda` por id, limiar e aviso contando candidatos.
- `test_offline.py`: seção 20 (10 checks: determinismo seed fixa, ids==nomes sem perfil, 12 candidatos questions, balanceamento, cédulas sem questões próprias, sem vazamento de nome em ids).

## Decisões tomadas em voo (fora do plano)
- Texto do candidato question = `pergunta\nRecomendacao: <rec>` — a recomendação FAZ PARTE do candidato (o par pergunta+recomendação é o que se ranqueia).
- Id `q<idx>-<n>`: idx = índice do membro na lista `members` (estável dentro do run, sem nome).
- Aviso do limiar reescrito para "3+ candidatos" (a checagem da seção 9 casa por substring "estagio 2 pulado", inalterada).
- Membro cujo bloco QUESTIONS não parseia → aviso nomeado "destilacao: <nome>: <erro>" e zero candidatos dele (falha nunca silenciosa).

## Pegadinhas descobertas
- O mock de falha da seção 9 permanece ativo até o fim da suite (glm falha no estágio 1) — asserts posteriores sobre "todos os membros" veem 3, não 4.
- `_rank_one` monta `por_rotulo` por lookup em elegiveis; rótulo→id→texto (o mapping do ballot continua rótulo→id no campo `label_to_member`, mantido pelo shape do registro).

## O que a próxima issue precisa saber
- Para #8: `consensus` agora carrega ids (default: nomes). `stage3` segue recebendo `blind_answers` (nome→texto) + consensus — a tabela cai para id cru quando não acha alias ( QUESTIONS path ); #8 deve passar `mode=profile.chairman_mode` e, no decider, `decision_prompt` sobre `{c.id: c.text}` + `parse_decision(reply.content, [c.id...])`; `spec.run_refs`/`bundle`/`profile` ainda não estão no `Run` (é seu); selo: perfis no `config_snapshot`.
- `order_members` no registro stage2 agora é lista de ids (default: nomes — shape idêntico).

## Pendências deixadas
- nenhuma
