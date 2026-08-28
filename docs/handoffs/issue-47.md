# Handoff — issue #47 (Tarefa 3: `--rank-lite`)
PR #<n> · branch issue/47-rank-lite (código em <sha12>) · 2026-08-28

## O que mudou no repo
- `council/engine.py`: campo aditivo `stage2_mode` no `Run` (default `"full"`, ausente
  em registro antigo = `"full"` — Emenda 2 selada); `stage2(lite=False)` seleciona os
  primeiros `max(2, len(answerers)//2)` avaliadores NA ORDEM DA CONFIG; `run(rank_lite=)`
  seta `stage2_mode="lite"` + warning "estágio 2 em modo lite (deliberação não plena):
  <n>/<m> avaliadores". Sem a flag, byte-idêntico ao atual.
- `council/cli.py`: `ask --rank-lite`; exclusivo com `--no-rank` e `--resume`
  (`rank_lite_invalid_args`, exit 2, nada gravado).
- `test_offline.py`: seção 32, +12 checks (438 total, exit 0); golden byte a byte.
- Estado anterior: T1 (`a0e6284`) e T2 (`51e1936`) merged; Emenda 2 pushed (`9eab0df`).

## Decisões tomadas em voo (fora do plano)
- Parcial lite sob o guarda da Tarefa 1 → `stage2_incomplete` (2/4 cédulas): resume de
  parcial lite segue fail-closed e manda reexecutar integral — estendê-lo é issue
  futura; teste prova o fail-closed.
- Warning usa n = cédulas geradas, m = respondentes elegíveis do estágio 1.

## Pegadinhas descobertas
- O chat global da suíte, desde a seção 9, é o wrapper que derruba o glm (429) e ele
  NUNCA é restaurado — seções novas que rodem `ask` completo precisam patchar o
  `fake_chat` localmente (seção 32(b) faz isso), senão respondem 3/4 em silêncio.

## O que a próxima issue precisa saber
- Tarefa 4 (auditor classificado): não toca engine; `stage2_mode` e `resumed_from` são
  os únicos campos novos do `Run` (Emenda 2 fecha o schema desta fase).
- O epilog do `ask` (T2) ainda não cita `--rank-lite`; se a issue quiser, é 1 linha.

## Pendências deixadas
- Resume de parcial lite (extensão futura, fora do escopo declarado).
- Epilog sem menção ao `--rank-lite` (só citado em `--help` da opção).
