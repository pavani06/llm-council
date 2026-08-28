# Resiliência do CLI — resume de parcial, help de execução, estágio 2 orçável e auditor classificado — Plano de Execução

**Objetivo:** implementar as 4 melhorias de produto derivadas do review da execução
de 28/08 (registro `d1adb36e046a` + parcial `483189`): retomada de parcial via
síntese, documentação de duração/execução desanexada, modo lite do estágio 2 e
classificação de termos no auditor.
**Fase:** Implementação (pré-issue; vira issues + diretivas pela rotina de relay do
AGENTS.md)
**Dependências:** Emenda 2 de schema (Tarefa 0) antes de qualquer campo novo no
`Run`; suite offline verde no estado atual.
**Duração estimada:** T0 ~30 min · T1 ~1 sessão · T2 ~30 min · T3 ~2 h · T4 ~2 h
**Issue:** #47 (epic que consolida T0-T4; diretivas por tarefa nos comentários)

---

## Contexto e evidência

- Parcial de hoje (`20260828T123200+0000-483189-partial.json`) morreu por SIGTERM
  externo com `stage_reached: stage2`, mas salvou `stage1` completo (4 candidates
  com reply) e `stage2` completo (4 rankers com `raw`/`verdicts`). Só a síntese
  (28.094 tokens no run completo) ficou faltando. Reexecutar tudo custou 230.799
  tokens; completar teria custado ~28k.
- Segunda ocorrência do modo de falha "timeout de processo" (r2 do grill e hoje).
- Território: `council/cli.py:56-94` (cmd_ask), `council/engine.py:353-543`
  (orquestração), `engine.py:579-624` (write_partial/save_run),
  `engine.py:144-157` (Interruption), `engine.py:340-351` (_checkpoint),
  `prompts.py:15-27` (ranking_prompt), `prompts.py:68-104` (chairman_prompt),
  `audit.py:50-94,138-166` (termos_especificos/auditar), `cli.py:712-724` (parser),
  `test_offline.py:450-505` (golden seção 15: ranking_prompt + chairman_prompt
  blind/open), `test_offline.py:1637-1676` (teste de parcial existente),
  `provenance.py:71-119` (config_snapshot/config_digest/seal).
- Constraint dura (texto-base §7 + Emenda 1): schema do `Run` congelado para o
  experimento — campo novo = emenda nomeada na seção 11. O experimento ainda não
  começou; os campos novos desta fase precisam entrar numa Emenda 2 ANTES do piloto.

## Constraints (orçamento: 6)

1. Golden §15 byte a byte intocado: nenhuma função de prompt muda; caminho default
   de execução comportamentalmente idêntico.
2. Campos novos no `Run` apenas aditivos (`resumed_from`, `stage2_mode`), com
   Emenda 2 selada antes do piloto; registros antigos em `runs/` jamais reescritos.
3. Resume NUNCA reescreve o parcial: produz registro novo que referencia o parcial
   por sha; o arquivo parcial permanece.
4. Falha nunca silenciosa: todo guard de resume/lite falha com erro nomeado e
   exit não-zero, sem gravar arquivo.
5. Stdlib pura; nenhuma dependência nova.
6. `.venv/bin/python test_offline.py` exit 0 ao fim de cada tarefa; CI `offline`
   verde.

---

### Tarefa 0: Emenda 2 de schema (gate)

**Artefatos:** Saída: entrada nova na seção 11 de
`docs/prereg/2026-08-27-experimento-1vsN.md` + anexo
`docs/prereg/2026-08-28-emenda-2.md`.

- [ ] **Passo 1:** Redigir Emenda 2 declarando os campos aditivos que esta fase
      introduz no `Run`: `resumed_from` (string|None — sha256 do parcial que
      originou o registro; None/ausente = execução integral) e `stage2_mode`
      ("full"|"lite"; ausente = "full", leitura retroativa). Motivo: as melhorias
      de resiliência não podem esperar o fim do piloto; campos declarados antes
      do piloto começar preservam o congelamento.
  Comando: `grep -c "Texto-base\|Motivo\|Ato do operador" docs/prereg/2026-08-28-emenda-2.md`
  Esperado: arquivo existe e contém os 4 campos do formato da Emenda 1; nesta
  fase o campo de ato está vazio (rascunho).
- [ ] **Passo 2:** PARAR para aprovação nomeada do operador; colar entrada na
      seção 11 só com a frase preenchida.
  Comando: `grep -A4 "### Emenda 2" docs/prereg/2026-08-27-experimento-1vsN.md && grep "Status: SELADA" docs/prereg/2026-08-28-emenda-2.md`
  Esperado: entrada na seção 11 com linha "Ato do operador:" seguida de data e
  frase não vazias; anexo com status SELADA.
  Critério: ambos os greps retornam conteúdo (exit 0); sem eles a tarefa não
  está completa.

### Tarefa 1: `council ask --resume <sha-parcial>` (síntese-only)

**Artefatos:** Entrada: parcial em `runs/` com `partial=true`, `stage_reached
>= stage2`, stage2 completo. Saída: registro novo (`<stamp>-<sha12>.json`)
referenciando o parcial; parcial preservado.

- [ ] **Passo 1:** CLI — `--resume` em `council/cli.py:717-724` (prefixo de sha,
      repetível não; mutuamente exclusivo com `--no-rank` e com pergunta
      posicional: se passados juntos, erro nomeado `resume_invalid_args`).
      Comando: `.venv/bin/python -c "from council.cli import build_parser; ..."`
      ou smoke manual `council ask --help`.
  Esperado: opção parseada; ajuda mostra o argumento.
- [ ] **Passo 2:** Carregamento e guards em `engine.py` (função nova
      `load_partial_for_resume()` perto de `write_partial`, `engine.py:579-600`),
      fail-closed com erros nomeados: `partial_not_found` (sha sem match em
      `runs/*.json`), `not_partial` (`partial != true`), `stage2_incomplete`
      (`stage_reached` < stage2, ou ballots < avaliadores elegíveis, ou algum
      `ok=false`), `config_drift` (`producer.config_sha256` do parcial != atual
      via `provenance.py:102-104`). Nenhum arquivo escrito em caso de erro.
  Comando: novo teste offline chamando a função com fixtures dos 4 casos.
  Esperado: 4 erros nomeados distintos, exit não-zero.
- [ ] **Passo 3:** Montagem do registro retomado em `Council.run()` (ramo novo
      antes de `stage1()`, `engine.py:399-413`): copiar verbatim de parcial:
      `question`, `seed`, `stage1`, `stage2`, `candidates`, `decision`;
      recalcular `consensus` com a função existente a partir dos ballots
      herdados (determinístico, sem rede); selar producer fresco (Tarefa 0 já
      garante config igual); campo novo `resumed_from = sha256 do parcial`;
      `warnings` com entrada "estágios 1-2 herdados de <sha12>"; pular direto
      para `stage3()`.
  Comando: teste offline com parcial fixture (4/4 ballots ok) + provider fake.
  Esperado: registro novo com `resumed_from`, stage1/stage2 idênticos byte a
  byte aos do parcial (`==` em dicts), consenso recomputado igual ao do
  parcial, síntese nova presente.
- [ ] **Passo 4:** Preservação do parcial: no caminho resume, `save_run()`
      (`engine.py:603-624`) NÃO remove o `<...>-partial.json` referenciado
      (remoção atual em `engine.py:609-611` vira condicional).
  Comando: teste offline que roda resume e afirma que o arquivo do parcial
  continua existindo.
  Esperado: parcial intacto + registro novo em `runs/`.
- [ ] **Passo 5:** Usage: `usage_by_stage` do registro novo = usage dos estágios
      herdados (copiado do parcial) + usage fresco da síntese; `total` = soma;
      campo histórico `usage` segue semântica de `engine.py:555-561`.
  Comando: teste offline somando usage do fixture.
  Esperado: `usage_by_stage.total` == soma exata; ledger `council cost` não
  quebra (smoke manual).
- [ ] **Passo 6:** Verificação da tarefa: golden §15 intocado (nenhum arquivo em
      `golden/` modificado no diff) e suite completa verde.
  Comando: `git status --porcelain golden/` vazio e
  `.venv/bin/python test_offline.py`.
  Esperado: exit 0.

### Tarefa 2: Help e README — duração esperada e execução desanexada

**Artefatos:** Saída: epilog em `cli.py:717-724`, seção do README.

- [ ] **Passo 1:** Epilog no parser `ask` (e nota curta na descrição do parser de
      topo, `cli.py:712-715`): duração esperada (4 membros + ranking + síntese ≈
      13-15 min medidos em 28/08), padrão desanexado (`setsid nohup council ask
      ... &` + polling do arquivo em `runs/`), e que SIGTERM externo salva
      parcial retomável com `--resume` (após Tarefa 1; escrever a menção só se
      T1 já mergeada).
  Comando: `council ask --help`.
  Esperado: epilog visível; suite verde (help não é prompt — golden intocado).
- [ ] **Passo 2:** README: seção "Executando deliberações longas" com o padrão
      desanexado, as 2 ocorrências registradas do modo de falha (r2, 28/08) e
      como inspecionar/recuperar parciais (`council show`, `--resume`).
  Comando: grep "Executando deliberações longas" README.md.
  Esperado: seção presente; suite verde.

### Tarefa 3: Estágio 2 orçável — `--rank-lite`

**Artefatos:** Saída: flag em `cli.py:717-724`, seleção em `engine.py:443-482`,
campo aditivo `stage2_mode` no `Run` (`engine.py:104-136`).

- [ ] **Passo 1:** Campo aditivo `stage2_mode` no `Run` com default "full";
      Emenda 2 (Tarefa 0) já cobre. Ausência do campo em registros antigos =
      "full" (convenção de leitura documentada no docstring de `Run`).
  Comando: teste offline instanciando `Run` sem o campo.
  Esperado: serialização/leitura não quebram; `asdict` inclui o campo novo.
- [ ] **Passo 2:** Flag `--rank-lite`: avaliadores do estágio 2 = primeiros
      `max(2, len(answerers)//2)` membros NA ORDEM DA CONFIG (determinístico,
      sem escolha por modelo). Warning nomeado no registro: "estágio 2 em modo
      lite (deliberação não plena): <n>/<m> avaliadores".
  Comando: teste offline com 4 answerers e flag ligada.
  Esperado: exatamente 2 ballots; `stage2_mode == "lite"`; warning presente;
  flag desligada = comportamento atual idêntico (ballots 4/4).
- [ ] **Passo 3:** `--rank-lite` incompatível com `--resume` e com `--no-rank`
      (erro nomeado `rank_lite_invalid_args`). Ranking/síntese usam as funções
      existentes (nenhum prompt muda — golden seguro).
  Comando: suite offline com os 3 casos de args.
  Esperado: erros nomeados; golden §15 intocado; suite exit 0.

### Tarefa 4: Auditor com classificação de termos

**Artefatos:** Saída: `council/audit.py` (`termos_especificos` 50-94, `auditar`
138-166) e saída de `cmd_audit` (`cli.py:521-569`).

- [ ] **Passo 1:** Classificador mecânico de shape (stdlib `re`, função nova
      `classificar_termo()`): "estrutural" = snake_case, dotted path, hex/numérico,
      sigla com dígitos, padrão `X-yy-zz` (ex.: "N-vs-1"); "prosa" = o resto
      (possível alegação factual). Heurística de forma, sem julgar verdade —
      limitação documentada no docstring.
  Comando: testes unitários com os 4 trechos reais do registro `d1adb36e046a`
  como fixtures (campos de manifest e "2.8" → estrutural; "N-vs-1" → estrutural).
  Esperado: classificação determinística, 4/4 casos reais classificados como
  estrutural.
- [ ] **Passo 2:** Saída do `council audit` em dois blocos: "acréscimos
      estruturais prováveis (nomeação própria do presidente)" e "acréscimos a
      verificar (possível alegação factual)" — com a nota existente de que quem
      julga é o operador. JSON (`--json` de audit, se existir) ganha o campo
      classificativo de forma aditiva.
  Comando: `council audit d1adb36e046a` (prefixo de sha; `audit` recebe sha,
  não caminho — `council/judgment.py:48-59`).
  Esperado: os 4 trechos de hoje todos no bloco estrutural; suite verde.

---

## Sequenciamento e gates

T0 (gate de schema) → T1 → T2 → T3 → T4. T2, T3, T4 são independentes entre si
depois de T0; a ordem acima é a de valor. Cada tarefa termina com suite offline
exit 0; cada virou issue própria com diretiva pela rotina de relay (pré-voo de
handoffs → diretiva → ciclo issue-start/review/gate humano/finish).

## Análise por Eixo

### Eixo 1 — Verificação e dependências
Zero dependências externas novas (stdlib pura). Gate de conclusão por tarefa:
`.venv/bin/python test_offline.py` exit 0 + golden `golden/` intocado (verificado
por `git status` nos fixtures). O gate transversal é a Emenda 2 (T0) sem a qual
T1 e T3 violam o congelamento de schema do pré-registro.

### Eixo 2 — Manutenção futura
`resumed_from` e `stage2_mode` são aditivos e retroativamente legíveis (ausente =
default), sem migração. O resume reusa `stage3()`/`chairman_prompt` existentes —
nenhum segundo caminho de síntese para manter. Risco de retrabalho baixo: se o
piloto 1-vs-N mudar o harness de rodadas (Fase 2), o resume atua sobre o `ask`
atual, cujo comportamento é protegido por golden e não faz parte do braço N.

### Eixo 3 — Impacto arquitetural
Toca o núcleo (`engine.py`) mas sem alterar fluxo de dados default: resume e lite
são ramos opt-in com guardas nomeados. Alinhado com a filosofia registrada
(composição de registros imutáveis por sha; nada stateful). Nenhum ADR novo
necessário: a decisão "resume por composição, não por mutação" repete a decisão
de multi-rodada já selada no pré-registro §9 e na Emenda 1 (item 5/6).

## Compliance gate

Canons aplicados: intent-five-part-primitive (objetivo/verificação por tarefa),
constraint-budget-gate (6 constraints explícitas). Desvio documentado: os demais
canons de lifecycle/brake foram avaliados e não mudam o plano (escopo curto, 4
tarefas independentes, gate operador na T0). Nenhum placeholder pendente; todos
os passos têm comando e esperado.
