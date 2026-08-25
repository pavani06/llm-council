# Handoff — issue #5 (T3)
PR #20 · branch issue/5-prompts-parametrizados (código em 695dfa57bf3f) · 2026-08-25

## O que mudou no repo
- `council/prompts.py`: `DEFAULT_CRITERIA` (fonte única dos 4 literais), `ranking_prompt(..., criteria=DEFAULT_CRITERIA)`, `chairman_prompt(..., mode="synthesizer", divided=False)` com tabela extraída para `_tabela_consensus` (compartilhada), `decision_prompt` nova, `stage1_user_prompt` nova, diretrizes `_STAGE1_DIRETIVAS` (questions/proposal).
- `test_offline.py`: seção 17 (18 checks).

## Decisões tomadas em voo (fora do plano)
- `decision_prompt(question, candidates, consensus, *, divided=False)`: recebe candidatos JÁ rotulados (dict não vazio — vazio levanta ValueError nomeado) (cegos ou não — quem rotula é o engine/#8); `chairman_prompt(mode="decider", divided=...)` delega para ela (assinatura compatível via answers).
- `stage1_user_prompt(question, bundle=None, stage1_format="prose")` — SEM role_hint: papel viaja como mensagem system no engine (#6), não no user prompt. Divida registrada aqui; #6 não deve reinventar.
- Diretrizes dos blocos pedem a gramática EXATA de structured.py (5 campos com pipes, 'nenhuma' como valor, palavra-cabeçalho proibida em outras linhas) — os prompts e o parser nasceram casados.

## Pegadinhas descobertas
- Editar o fim do `test_offline.py` com âncoras em prints de seção é frágil: a ordem física é 15→18→16→17 (a 16 nasceu após a 18); ancorar no print errado embaralha seções. Reordenado por script com marcadores.
- Golden provou byte-identidade DEPOIS de extrair a tabela do chairman para helper — extração segura só porque a seção 15 existe.

## O que a próxima issue precisa saber
- Contratos para #6/#8:
  - `ranking_prompt(question, labelled, criteria)` — criteria do perfil (`profile.criteria or DEFAULT_CRITERIA`);
  - `chairman_prompt(question, answers, consensus, blind=..., mode=..., divided=...)` — mode do `profile.chairman_mode`; `divided` = `rec.divided`;
  - `stage1_user_prompt(question, bundle, profile.stage1_format)` — sem perfil: NÃO chamar (ou chamar com (question) que devolve a pergunta inalterada);
  - `decision_prompt` espera `candidates` como dict rotulo→texto.
- #8: resposta do decider parseia com `parse_decision(reply.content, list(candidates))`.

## Pendências deixadas
- nenhuma
