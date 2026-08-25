# Handoff — issue #6 (T5)
PR #<n> · branch issue/6-engine-spec (código em f327cf82f475) · 2026-08-25

## O que mudou no repo
- `council/engine.py`: dataclass `Deliberation(question, profile=None, bundle=None, run_refs=[])`; `run(str | Deliberation)`; `_ask_one`/`stage1` recebem a spec e montam mensagens com papel.
- `test_offline.py`: seção 19 (8 checks com captura completa de mensagens).

## Decisões tomadas em voo (fora do plano)
- Matriz de mensagens do estágio 1: **sem perfil** → `[user: pergunta]` (byte a byte igual ao histórico); **com perfil** → user é SEMPRE `stage1_user_prompt(question, bundle, fmt)` para todos; membro com papel ganha `[system: papel]` antes. Sem papel ≠ sem bundle — todos veem o contexto.
- `run` cria `question = spec.question` como alias para o corpo existente (scrub/stage2/stage3 intocados); `run_refs` ainda não entra no `Run` (é a #8).

## Pegadinhas descobertas
- Captura de estágio 1 nos testes: filtrar por conteúdo das mensagens ("FINAL RANKING"/"preside" excluem estágios 2-3) — o mock global VISTOS só grava a primeira mensagem.
- Ao trocar assinatura de `run`, TODO uso interno de `question` precisa do alias (o scrub usa `.lower()` — estoura em Deliberation, não em str).

## O que a próxima issue precisa saber
- Para #7 (candidatos): a destilação entra ENTRE `stage1` e `stage2` no `run` — respostas ok chegam como `dict[name→content]`; `spec.profile.stage1_format` decide prose/proposal (1 candidato por resposta) vs questions (`parse_questions` por resposta, autor = membro). Scrub de identidade ANTES da destilação (questões nascem cegas).
- Para #8: `spec.run_refs`/`spec.bundle` existem na spec mas AINDA não vá para o registro — é seu; `stage3` já pode receber `mode=profile.chairman_mode` via prompts (contrato no handoff da #5).
- Criteria do perfil: `profile.criteria or DEFAULT_CRITERIA` no ranking_prompt (#7).

## Pendências deixadas
- nenhuma
