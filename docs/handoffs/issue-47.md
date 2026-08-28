# Handoff — issue #47 (Tarefa 4: auditor classificado)
PR #<n> · branch issue/47-auditor-classificado (código em <sha12>) · 2026-08-28

## O que mudou no repo
- `council/audit.py`: `classificar_termo()` (heurística de FORMA: "estrutural" =
  snake_case, dotted.path, hex com dígito, número, sigla com dígitos, X-yy-zz;
  "prosa" = restante) — limitação "não julga verdade" no docstring; `Acrescimo.classes`
  aditivo (classe por termo, mesma ordem) + `.estrutural` (todos estruturais);
  `Auditoria.estruturais`/`.a_verificar` particionam. Extração (`termos_especificos`)
  intocada — nada mudou no QUE é flagado.
- `council/cli.py`: `cmd_audit` imprime dois blocos — "acréscimos estruturais prováveis
  (nomeação própria do presidente)" e "acréscimos a verificar (possível alegação
  factual)" — mantendo a nota de que quem julga é o operador.
- `test_offline.py`: seção 33, +15 checks (453 total, exit 0); golden byte a byte;
  `prompt_verificacao` intocado.
- Smoke real (máquina do operador): `council audit d1adb36e046a` → 4/4 trechos no
  bloco estrutural, bloco de verificação vazio.

## Decisões tomadas em voo (fora do plano)
- Hex exige ≥ 1 dígito e ≥ 6 chars: "defaced" (tudo letras hex) seria falso
  estrutural; shas/reais sempre têm dígito.
- Título dos blocos sem acento (convenção das strings de CLI do repo; a issue cita
  com acento — forma, não contrato).
- Trecho vai ao bloco estrutural só com TODOS os termos estruturais; 1 prosa manda
  para verificação (conservador).

## Pegadinhas descobertas
- `python -m council audit X --config Y` não parseia: `--config` é global e vai
  ANTES do subcomando.

## O que a próxima issue precisa saber
- Épico #47 completo (T0-T4). `Acrescimo.classes` é aditivo: consumidores antigos
  (cmd_ask, cortesia) seguem funcionando.
- Fase 2 (experimento 1-vs-N) pode começar: schema selado com Emenda 2, pushed.

## Pendências deixadas
- `--json` no audit segue inexistente (fora de escopo declarado); classificação
  hoje só na estrutura de dados e nos blocos de texto.
