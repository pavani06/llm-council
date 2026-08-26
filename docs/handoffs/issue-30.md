# Handoff — issue #30 (C1)
PR #36 · branch issue/30-checkpoint (código em 934ccdbf761f) · 2026-08-26

## O que mudou no repo
- `council/runs.py` (novo, folha, só stdlib): `PARTIAL_SUFFIX`, `stamp_for`, `partial_path`, `final_runs`. Dono único de "o que é parcial".
- `council/engine.py`: `Run` ganha `partial`/`stage_reached`/`interrupted`/`interruption_reason` (aditivos, default neutro); `Interruption` (flag que o handler marca) e `RunInterrupted`; `write_partial` (cópia marcada via `replace`, usage acumulado, troca atômica `.tmp`→rename) e `finalize_run` (`save_run` e só então apaga o parcial); `Council.run(..., runs_dir=None, interruption=None)` com checkpoint em 4 limites: `seal`, `stage1`, `stage2`, `synthesis`.
- `council/cli.py`: `ask` e `deliberate` armam SIGINT/SIGTERM (`_sinais_armados`, restaura os anteriores), passam `runs_dir`/`interruption`, finalizam por `finalize_run`, e em `RunInterrupted` imprimem erro nomeado e saem 130; `show` e `--ref` leem por `final_runs`.
- `council/mcp_server.py`: mesmo ciclo (engine dono do checkpoint); `_falha_de_registro` nomeia o `OSError` do save final citando o parcial preservado, no log e no retorno; `run_refs` lê por `final_runs`.
- `council/judgment.py`: `carregar` lê por `final_runs` (docstring de módulo folha atualizada).
- `test_offline.py`: seção 26, 24 checks, casos (a)-(e). Suite 337 checks exit 0; golden (seção 15) byte a byte.

## Decisões tomadas em voo (fora do plano)
- **`pid` no nome do parcial** (`<stamp>-<pid>-partial.json`): o carimbo tem granularidade de segundo e o experimento 1-vs-N roda braços em paralelo — dois braços no mesmo segundo se sobrescreveriam. Contra o final não há colisão (final termina em `<sha12>.json`).
- **Leitores passam a ignorar parciais** (`show`, `--ref` do CLI e do MCP, `judgment.carregar`). Sem isso o parcial entraria como registro final — falha silenciosa, e um veredito de `council ab` endereçado a execução incompleta corromperia o corpus. Nasceu daí o módulo `runs.py`: `judgment` é folha e não podia importar `engine`.
- **Troca atômica** na escrita do parcial: sem ela, morte no meio da escrita truncaria o parcial e apagaria junto o limite anterior — exatamente o que o mecanismo existe para salvar.
- **`elapsed_s` no parcial** além do `usage` que a issue pede: parcial com `0.0s` mentiria sobre quanto tempo foi gasto.
- Interrupção **não grava registro final**: o artefato é o parcial com `interrupted=true`. Final com `interrupted` seria execução incompleta entrando no denominador como se tivesse terminado.

## Pegadinhas descobertas
- `Ctrl-C` não aborta na hora: marca a interrupção e o fluxo para no **próximo limite de estágio** (threads de chamada não são interrompíveis; foi verificado num terminal real, parou em `stage2` depois de as cédulas já pagas entrarem). Quem quiser matar na hora usa SIGKILL — e o parcial do último limite sobrevive (verificado).
- `save_run` nunca é mais chamado direto pelos chamadores; quem chamar sem `finalize_run` deixa parcial órfão em disco.
- `Council.run` sem `runs_dir` não faz checkpoint algum (compatibilidade: toda a suíte anterior e uso como biblioteca seguem iguais).

## O que a próxima issue precisa saber
- **#31 (C2)** acrescenta campos ao `Ballot`/`usage_by_stage`: eles entram no parcial de graça (o snapshot é `replace(rec, ...)`), mas o `usage` do parcial vem de `_total_usage`, que hoje soma só estágio 1 + presidente — ao mudar `_total_usage`, o parcial acompanha sozinho.
- **#34 (C5)** deriva custo dos registros: use `runs.final_runs()` para varrer, nunca `glob("*.json")`, senão parciais entram no ledger. `partial=true` é o marcador redundante para quem ler conteúdo.
- Lista aditiva do schema até aqui: `partial`, `stage_reached`, `interrupted`, `interruption_reason`.

## Pendências deixadas
- `council/mcp_server.py:11` importa `asdict` sem uso — já era assim antes desta issue; não toquei (edição cirúrgica).
- Não existe comando de varredura de parciais órfãos (fora de escopo declarado na diretiva); a detecção hoje é `ls *-partial.json`.
