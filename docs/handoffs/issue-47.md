# Handoff — issue #47 (Tarefa 1: `--resume`)
PR #48 · branch issue/47-resume-sintese (código em d1384c1) · 2026-08-28

## O que mudou no repo
- `council/cli.py`: `ask --resume SHA_PARCIAL`; exclusivo com `--no-rank`/pergunta
  (`resume_invalid_args`, exit 2); stdin nunca lido no modo resume.
- `council/engine.py`: `load_partial_for_resume()` com guardas fail-closed nomeados
  (`partial_not_found` c/ prefixo ambíguo, `not_partial`, `stage2_incomplete`,
  `config_drift`) via `ResumeError`, nada gravado; `_herdar_estagios()` copia estágios
  1-2 verbatim e RECOMPUTA consenso pela borda (sem rede); campo aditivo `resumed_from`
  no `Run` (Emenda 2 selada 28/08, master `3ddb236`); cegamento recriado pelo mesmo scrub.
- `council/runs.py`: `partial_path(..., resumed=False)` — rastro do resume com sufixo `-r`.
- `test_offline.py`: seção 30, +30 checks (423 total, exit 0); golden byte a byte.

## Decisões tomadas em voo (fora do plano)
- **Sufixo `-r`**: colisão real no teste — resume no mesmo segundo/processo (mesmo pid)
  sobrescrevia o parcial referenciado no "seal" e o apagava no finalize. O nome do
  rastro deriva de `resumed_from` (setado antes do 1º checkpoint): escrita e remoção
  condicionais ao flag — a "condição" que a issue previa.
- **`members` copiado verbatim** (fora da lista): os estágios herdados pertencem àquele
  roster. Re-scrub determinístico: config igual (guarda) → mesmo cegamento.

## Pegadinhas descobertas
- `settings.runs_dir` entra no `config_sha256`: mudá-lo entre selo e resume é drift.
- `stage_reached == "synthesis"` é retomável e RE-RODA a síntese (gasto, não corrupção).
- Prefixo ambíguo falha como `partial_not_found` com mensagem própria.

## O que a próxima issue precisa saber
- Tarefa 3: `stage2_mode` já coberto pela Emenda 2; leitura retroativa testada.
- Ledger/`final_runs()` já classificam `-r-partial.json` como parcial (sufixo comum).
- `usage_by_stage.total` do resume = herdado + síntese fresca (soma exata, testado).

## Pendências deixadas
- Parcial de `deliberate` (perfil) via `ask`: herda estágios, sintetiza em synthesizer.
- Varredura de parciais órfãos (inclui `-r`) continua inexistente (pendência da C1).
