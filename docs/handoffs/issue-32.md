# Handoff — issue #32 (C3)
PR #<n> · branch issue/32-decision-aliases (código em <sha12>) · 2026-08-26

## O que mudou no repo
- `council/engine.py`: `Run.decision_aliases: dict[str, str]` (aditivo, default `{}`) e uma linha que o preenche logo após o laço que monta `alias_decisao`, **invertido** — a chave é o rótulo que aparece no texto do presidente (`"Candidato B"`) e o valor é o id real. Nada mais mudou no arquivo.
- `test_offline.py`: seção 21 estendida com o caso `(k)`, 6 checks. Suite 363 checks exit 0; golden (seção 15) byte a byte.

## Decisões tomadas em voo (fora do plano)
- **A linha que des-aliasa a `escolha` ficou intocada** (`engine.py:513-514`), embora ela inverta o mesmo dict uma segunda vez e pudesse passar a ler `rec.decision_aliases`. O handoff da #8 registra que esse é o ponto onde o vazamento de identidade quase passou; uma dict-comprehension duplicada custa menos que mexer ali. Se alguém unificar depois, o caso (k) já cobre o comportamento.
- **`{}` com `blind_chairman=False` é resposta, não omissão**: sem cegamento os ids já vão crus para o presidente e não há alias a resolver. Provado no caso (k).
- Verificação de "registro antigo lê neutro" ficou compacta (um `.get` sobre dict sem o campo, mais o caminho synthesizer): a leitura de registro legado pelos leitores reais — `council show`, `judgment.carregar`, `audit.auditar` — já é coberta pela seção 27, criada na #31.

## Pegadinhas descobertas
- O `decision_prompt` começa com "Voce preside um conselho que precisa DECIDIR", ou seja, contém o substring `"preside um conselho"` que os mocks usam para detectar o estágio 3 synthesizer. Qualquer fixture novo precisa testar `"precisa DECIDIR"` ANTES — pegadinha já registrada na #8 e que reapareceu no provedor falso do QA manual.
- Os rótulos seguem a ordem do consenso, não a ordem dos membros: no QA, `Candidato A` caiu no conselheiro `tres`. É por isso que reconstruir o mapa de fora exigia ler o código; agora não exige mais.

## O que a próxima issue precisa saber
- **#33 (C4)** muda o que "candidato" significa (destila `proposal`): `decision_aliases` continua sendo rótulo → `candidate.id`, então quando o id deixar de ser o nome do membro o mapa acompanha sozinho — mas quem consumir o mapa esperando nome de conselheiro tem de passar a cruzar com `candidates[].author`.
- **#34 (C5)** não depende deste campo.
- Lista aditiva do schema até aqui: `partial`, `stage_reached`, `interrupted`, `interruption_reason` (C1); `usage_by_stage` no `Run` e `usage`/`latency_s` por cédula (C2); `decision_aliases` (C3).

## Pendências deixadas
- O texto do presidente permanece cru, com os rótulos cegos dentro de `dissidencias` e `fundamentos` (fora de escopo declarado na issue): o mapa resolve, mas quem exibir o texto ao humano ainda precisa traduzir na hora da exibição.
