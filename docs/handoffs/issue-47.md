# Handoff — issue #47 (Tarefa 2: help e README desanexados)
PR #<n> · branch issue/47-help-readme (código em <sha12>) · 2026-08-28

## O que mudou no repo
- `council/cli.py`: epilog no subparser `ask` (duração 13-15 min medida em 28/08, 806 s
  no `d1adb36e046a`; padrão `setsid nohup` + polling de `runs/`; SIGTERM salva parcial
  retomável com `--resume`) e nota na descrição do parser de topo. Zero comportamento.
- `README.md`: seção "Executando deliberações longas" dentro de `## Uso` — padrão
  desanexado, as 2 ocorrências do modo de falha (r2 do grill em
  `docs/grill/sessao-fase2.md`; 28/08 com o parcial `483189`) e recuperação via
  `council show` + `--resume`.
- `test_offline.py`: seção 31, +3 checks (426 total, exit 0); golden byte a byte.
- Estado anterior: Tarefa 1 (`--resume`) merged em `a0e6284` (PR #48); Emenda 2 selada.

## Decisões tomadas em voo (fora do plano)
- Seção do README como subseção de `## Uso` (é sobre rodar `ask`), não seção de topo.
- CLI sem acentos (padrão do código); README com acentos (padrão do arquivo).
- Duração citada com a medição real (806 s, `d1adb36e046a`), não número redondo.

## Pegadinhas descobertas
- `add_parser(..., epilog=...)` com formatter default faz wrap sozinho — texto corrido
  funciona; o teste via `format_help()` cobre o texto mesmo embrulhado.

## O que a próxima issue precisa saber
- Tarefa 3 (`--rank-lite`): `stage2_mode` já coberto pela Emenda 2 (selada); erros
  nomeados seguem a convenção de código + `ResumeError` estabelecida na Tarefa 1.
- O epilog do `ask` cita `--resume`: se T3 citar flags no epilog, lembrar que
  `--rank-lite` é incompatível com `--resume` e `--no-rank`.

## Pendências deixadas
- Estimativa de duração/custo melhorada segue issue separada (fora de escopo aqui).
- Push da Emenda 2 (`f0e6af5`) ao `origin/master` pendente de ordem do operador.
