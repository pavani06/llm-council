# Handoff — issue #47 (Tarefa 1: `--resume`)
PR #<n> · branch issue/47-resume-sintese (código em <sha12>) · 2026-08-28

## O que mudou no repo
- `council/cli.py`: opção `--resume SHA_PARCIAL` no `ask`; exclusiva com `--no-rank` e
  com pergunta posicional (`resume_invalid_args`, exit 2); stdin nunca lido nesse modo.
- `council/engine.py`: `load_partial_for_resume()` com 4 guardas fail-closed nomeados
  (`partial_not_found` inclui prefixo ambíguo, `not_partial`, `stage2_incomplete`,
  `config_drift`) via `ResumeError` (código + msg, nada gravado); `_herdar_estagios()`
  copia estágios 1-2 verbatim e RECOMPUTA consenso pela borda (determinístico); campo
  aditivo `resumed_from` no `Run` (Emenda 2 selada 28/08 16:01, master `3ddb236`);
  cegamento da síntese reconstituído pelo mesmo scrub (config igual garantida pelo guarda).
- `council/runs.py`: `partial_path(..., resumed=False)` — parcial de execução retomada
  ganha sufixo `-r` (`<stamp>-<pid>-r-partial.json`).
- `test_offline.py`: seção 30, 30 checks novos (423 total, exit 0); golden byte a byte.

## Decisões tomadas em voo (fora do plano)
- **Sufixo `-r` no parcial do resume**: colisão REAL achada no teste — resume no mesmo
  segundo e processo (mesmo pid) fazia o checkpoint "seal" SOBRESCREVER o parcial
  referenciado e o finalize APAGÁ-lo. Nome do rastro do resume deriva de
  `resumed_from`; escrita e remoção ficam condicionais ao flag (era a "condição na
  remoção" que a issue previa). `resumed_from` é setado antes do 1º checkpoint.
- **`members` copiado verbatim do parcial** (não estava na lista da issue): coerência —
  os estágios herdados pertencem àquele roster.
- **Re-scrub determinístico**: `config_drift` garante mesma config → mesmos termos →
  re-scrub do conteúdo original reproduz o cegamento original.
- O final do resume apaga só o rastro `-r` próprio; o referenciado nunca tem caminho
  de remoção (seção 30 prova o arquivo intacto).

## Pegadinhas descobertas
- `settings.runs_dir` entra no `config_sha256`: mudá-lo entre selo e resume é
  `config_drift` (correto e fail-closed).
- `stage_reached == "synthesis"` é retomável e RE-RODA a síntese (gasto extra, não
  corrupção — síntese anterior fica só no parcial).
- Prefixo ambíguo (2+ registros) falha como `partial_not_found` com mensagem própria.

## O que a próxima issue precisa saber
- Tarefa 3: `stage2_mode` já tem cobertura da Emenda 2; o `Run` aceita o campo com
  default neutro na leitura de registros antigos.
- Ledger/`council cost` não mudou: `-r-partial.json` termina em `-partial.json`, então
  ledger e `final_runs()` já o classificam como parcial.
- `usage_by_stage.total` do resume = herdado + síntese fresca (soma exata, testado).

## Pendências deixadas
- Parcial de `deliberate` (com perfil) resumido via `ask` herda estágios e sintetiza
  em modo synthesizer — registro coerente, fora do escopo declarado, não bloqueado.
- Varredura de parciais órfãos (inclui `-r`) segue inexistente (já pendente da C1).
