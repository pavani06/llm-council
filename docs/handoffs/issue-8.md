# Handoff — issue #8 (T7)
PR #<n> · branch issue/8-registro-decider (código em 6b7f81628014) · 2026-08-25

## O que mudou no repo
- `council/engine.py`: campos aditivos no `Run` (`profile_name`, `bundle_sha256`, `run_refs`, `candidates`, `decision`); estágio 3 roteado por `chairman_mode` (synthesizer=default; decider via `decision_prompt` com `divided`); decider com `blind_chairman` exibe candidatos como `Candidato A/B/…` (ordem do consensus) e **des-aliasa a escolha** antes de gravar; parse falho → warning "estagio 3: decisao ilegivel — <erro>".
- `council/provenance.py`: `config_snapshot` ganha `"profiles"` (roles/criteria/chairman_mode/stage1_format; criteria None → null) — perfis mudam o `config_sha256`.
- `test_offline.py`: seção 21 (16 checks, casos (a)-(g) da diretiva).

## Decisões tomadas em voo (fora do plano)
- **Decider cego por rótulo**: a diretiva dizia `{c.id: c.text}` direto, mas em `proposal` id = nome de membro — com `blind_chairman=True` (default) isso vazaria identidade para o presidente. Candidatos e tabela exibidos como `Candidato <letra>` (ordem do consensus, estável); `parse_decision` valida os rótulos; `escolha` é traduzida de volta ao id real antes do registro.
- `bundle=""` → `bundle_sha256=None` (vazio = ausente, coerente com #5).
- Uma única chamada de presidente em ambos os modos; síntese cru segue em `rec.synthesis` mesmo no decider.

## Pegadinhas descobertas
- `decision_prompt` começa com "Voce preside um conselho que precisa DECIDIR" — contém o substring "preside um conselho" que os mocks da suite usam para detectar o estágio 3 synthesizer. Distinguir por "precisa DECIDIR" (ver antes na ordem de checagem).
- `stage3(..., divided=True)` só afeta o PROMPT; a resposta ser ENCALHADO é decisão do modelo — teste (e) captura o prompt e parseia a resposta separadamente.

## O que a próxima issue precisa saber
- **Shape do registro de deliberação** (para #9 CLI e #10 MCP): `profile_name: str|None`, `bundle_sha256: str|None` (sha256 do CONTEÚDO; texto nunca no registro — audit (#9) recebe o texto em memória no `deliberate` ou via flag `--bundle` com conferência de hash), `run_refs: [sha256...]`, `candidates: [{id,text,author}]`, `decision: {status,escolha,confianca,dissidencias,fundamentos}|None` (escolha sempre id real).
- CLI `deliberate` (#9): monta `Deliberation(question, cfg.profiles[nome], bundle_text, refs)` e chama `run(spec)`; `--json` já leva `asdict(rec)` — campos novos saem de graça.
- Selo mudou: registros novos carregam `config.profiles`; `council show` em registros antigos segue lendo (campo ausente = sem perfis).

## Pendências deixadas
- nenhuma
